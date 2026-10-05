import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(frontend, '..');
const sourceRoot = path.join(frontend, 'src');
const serviceRoot = path.join(sourceRoot, 'services');
const serviceNames = new Set();
const serviceRoutes = new Map();
const activeUses = new Map();

function parse(file) {
  return ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true,
    file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
}

function text(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isTemplateExpression(node)) {
    return node.head.text + node.templateSpans.map(span => {
      const name = span.expression.getText().replace(/[^a-zA-Z0-9_]/g, '_');
      return `:${name}` + span.literal.text;
    }).join('');
  }
  return null;
}

function normalizePath(value) {
  if (!value?.startsWith('/')) return null;
  return '/api/v1' + value.split('?')[0].replace(/:[a-zA-Z0-9_]+/g, ':id');
}

function requests(node) {
  const found = [];
  function visit(current) {
    if (ts.isCallExpression(current)) {
      let method = null;
      const expression = current.expression;
      if (ts.isIdentifier(expression)) {
        method = { getData: 'GET', downloadFile: 'GET', uploadFile: 'POST' }[expression.text] ?? null;
      } else if (ts.isPropertyAccessExpression(expression)
        && ts.isIdentifier(expression.expression) && expression.expression.text === 'api') {
        method = { get: 'GET', post: 'POST', patch: 'PATCH', put: 'PUT', delete: 'DELETE' }[expression.name.text] ?? null;
      }
      const url = current.arguments[0] && text(current.arguments[0]);
      const route = normalizePath(url);
      if (method && route) found.push(`${method} ${route}`);
    }
    ts.forEachChild(current, visit);
  }
  visit(node);
  return found;
}

function addService(name, node) {
  if (!ts.isObjectLiteralExpression(node)) return;
  serviceNames.add(name.split('.')[0]);
  for (const property of node.properties) {
    if (!ts.isPropertyAssignment(property) && !ts.isMethodDeclaration(property)) continue;
    const key = property.name?.getText().replace(/^['"]|['"]$/g, '');
    if (!key) continue;
    const full = `${name}.${key}`;
    const body = property.initializer ?? property.body;
    if (!body) continue;
    if (ts.isObjectLiteralExpression(body)) {
      addService(full, body);
      continue;
    }
    if (ts.isCallExpression(body) && ts.isIdentifier(body.expression)
      && body.expression.text === 'resource') {
      const base = body.arguments[0] && text(body.arguments[0]);
      if (base) {
        for (const [methodName, method, suffix] of [
          ['list', 'GET', ''], ['get', 'GET', '/:id'], ['create', 'POST', ''],
          ['update', 'PATCH', '/:id'], ['remove', 'DELETE', '/:id'],
        ]) serviceRoutes.set(`${full}.${methodName}`, [`${method} ${normalizePath(base + suffix)}`]);
      }
      continue;
    }
    serviceRoutes.set(full, requests(body));
  }
}

for (const file of fs.readdirSync(serviceRoot).filter(name => name.endsWith('.ts'))) {
  const parsed = parse(path.join(serviceRoot, file));
  for (const statement of parsed.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.initializer) {
        addService(declaration.name.text, declaration.initializer);
      }
    }
  }
}

function resolveImport(file, specifier) {
  const base = specifier.startsWith('@/') ? path.join(sourceRoot, specifier.slice(2))
    : specifier.startsWith('.') ? path.resolve(path.dirname(file), specifier) : null;
  if (!base) return null;
  for (const suffix of ['', '.ts', '.tsx', '/index.ts', '/index.tsx']) {
    const candidate = base + suffix;
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
  }
  return null;
}

const visited = new Set();
function traverse(file) {
  if (visited.has(file)) return;
  visited.add(file);
  const parsed = parse(file);
  for (const statement of parsed.statements) {
    if (ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier)) {
      const target = resolveImport(file, statement.moduleSpecifier.text);
      if (target) traverse(target);
    }
  }
  if (file.startsWith(serviceRoot + path.sep)) return;
  function visit(node) {
    if (ts.isPropertyAccessExpression(node)) {
      const parts = [];
      let current = node;
      while (ts.isPropertyAccessExpression(current)) {
        parts.unshift(current.name.text);
        current = current.expression;
      }
      if (ts.isIdentifier(current) && serviceNames.has(current.text)) {
        const name = [current.text, ...parts].join('.');
        if (serviceRoutes.has(name)) {
          const sources = activeUses.get(name) ?? new Set();
          sources.add(path.relative(root, file));
          activeUses.set(name, sources);
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(parsed);
}
traverse(path.join(sourceRoot, 'routes/index.tsx'));

const routeUses = new Map();
for (const file of visited) {
  if (file.startsWith(serviceRoot + path.sep)) continue;
  for (const route of requests(parse(file))) {
    const sources = routeUses.get(route) ?? new Set();
    sources.add(path.relative(root, file));
    routeUses.set(route, sources);
  }
}
for (const [method, files] of activeUses) {
  for (const route of serviceRoutes.get(method) ?? []) {
    let expanded = [route];
    if (route === 'GET /api/v1/reports/:id/:id') {
      const selections = new Set();
      for (const file of files) {
        const source = fs.readFileSync(path.join(root, file), 'utf8');
        for (const match of source.matchAll(/value:\s*['"]([a-z]+):([a-z-]+)['"]/g)) {
          selections.add(`GET /api/v1/reports/${match[1]}/${match[2]}`);
        }
        for (const match of source.matchAll(/reportsService\.get\(\s*['"]([a-z]+)['"]\s*,\s*['"]([a-z-]+)['"]/g)) {
          selections.add(`GET /api/v1/reports/${match[1]}/${match[2]}`);
        }
      }
      expanded = selections.size ? [...selections] : [route];
    }
    for (const concrete of expanded) {
      const sources = routeUses.get(concrete) ?? new Set();
      for (const file of files) sources.add(file);
      routeUses.set(concrete, sources);
    }
  }
}
const php = spawnSync('php', ['-r', 'require "hostinger-api/vendor/autoload.php"; echo json_encode(Anicraze\\Http\\RouteCatalog::definitions());'],
  { cwd: root, encoding: 'utf8' });
if (php.status !== 0) throw new Error('PHP route catalog could not be loaded: ' + php.stderr);
const phpRoutes = new Set(JSON.parse(php.stdout).map(([method, route]) =>
  `${method} ${route.replace(/:[a-zA-Z0-9_]+/g, ':id')}`));
const missing = [...routeUses.keys()].filter(route => !phpRoutes.has(route)).sort();
console.log(`Active frontend routes: ${routeUses.size}`);
console.log(`PHP-covered active routes: ${routeUses.size - missing.length}`);
console.log(`Missing active routes: ${missing.length}`);
if (process.argv.includes('--list')) {
  for (const route of [...routeUses.keys()].sort()) {
    console.log(`${phpRoutes.has(route) ? 'COVERED' : 'MISSING'} ${route} ← ${[...routeUses.get(route)].sort().join(', ')}`);
  }
}
for (const route of missing) console.log(`MISSING ${route} ← ${[...routeUses.get(route)].join(', ')}`);
if (!activeUses.size || !routeUses.size) throw new Error('No reachable frontend requests were found; parity gate cannot pass');
if (missing.length) process.exitCode = 1;
