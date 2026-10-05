"""Export the registered FastAPI contract for a future PHP parity migration.

This is source introspection only; no database connection or service call occurs.
Run with a harmless local DATABASE_URL and SECRET_KEY because app import needs
settings. The result deliberately marks unproven semantic fields for review.
"""

import inspect
import json
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app
from app.permissions.dependencies import SALES_ROUTES

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "php-migration-api-contract.json"
SUMMARY_PATH = ROOT / "docs" / "php-migration-api-contract.md"


def dependencies(route: APIRoute) -> list[dict]:
    found = []

    def walk(nodes):
        for node in nodes:
            call = node.call
            name = getattr(call, "__name__", type(call).__name__)
            closure = getattr(call, "__closure__", None) or ()
            captured = [cell.cell_contents for cell in closure]
            if name == "validator" and captured:
                requirements = sorted(str(value) for value in captured[0]) if isinstance(captured[0], set) else []
                validator_source = inspect.getsource(call)
                if "required_roles" in validator_source:
                    combination = "any_role"
                elif "expected.issubset(granted)" in validator_source:
                    combination = "all_permissions"
                elif "expected.intersection(granted)" in validator_source:
                    combination = "any_permission"
                else:
                    combination = "REVIEW_REQUIRED"
                found.append({"dependency": "authorization_validator", "required_values": requirements,
                              "combination": combination})
            elif name in {"require_owner", "require_admin"}:
                found.append({"dependency": name})
            walk(node.dependencies)

    walk(route.dependant.dependencies)
    return found


def main() -> None:
    spec = app.openapi()
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    operations = []
    for route in routes:
        source_file = inspect.getsourcefile(route.endpoint)
        source = inspect.getsource(route.endpoint)
        line = inspect.getsourcelines(route.endpoint)[1]
        relative = str(Path(source_file).resolve().relative_to(ROOT)) if source_file else None
        for method in sorted(route.methods):
            operation = spec.get("paths", {}).get(route.path, {}).get(method.lower(), {})
            # /health intentionally excludes OpenAPI but is still a registered route.
            sales = "allowed_route_only" if (method, route.path) in SALES_ROUTES else "denied_by_sales_allowlist"
            if route.path in {"/health", "/api/v1/health"} or route.path.startswith("/api/v1/auth/"):
                sales = "public_or_self_service"
            operations.append({
                "method": method,
                "path": route.path,
                "name": route.name,
                "operation_id": operation.get("operationId"),
                "source": {"file": relative, "line": line},
                "authorization_dependencies": dependencies(route),
                "sales_route_policy": sales,
                "request_body": operation.get("requestBody"),
                "parameters": operation.get("parameters", []),
                "responses": operation.get("responses", {}),
                "declared_success_status": route.status_code or 200,
                "request_validation": "FastAPI/Pydantic schema and parameter constraints; see components.schemas",
                "error_format": {"message": "string", "error": {"code": "string", "request_id": "string"}},
                "database_operations": "REVIEW_REQUIRED: endpoint may delegate to a service/repository",
                "transaction_boundary": "REVIEW_REQUIRED: inspect service and dependency commit/rollback semantics",
                "locking_behavior": "REVIEW_REQUIRED: inspect service/repository row/advisory locks",
                "shop_scope": "REVIEW_REQUIRED: route policy alone is not a data-scope proof",
                "endpoint_source_hints": {
                    "uses_service_or_repository": "service(" in source or "Service(" in source or ".repo." in source,
                    "mentions_scope": "scoped_shop(" in source or "assigned_store_id" in source,
                },
                "php_parity_status": "NOT_IMPLEMENTED",
            })
    operations.sort(key=lambda item: (item["path"], item["method"]))
    payload = {
        "source": "registered FastAPI APIRoute plus app.openapi() at local HEAD",
        "route_count": len(operations),
        "openapi_version": spec.get("openapi"),
        "components": spec.get("components", {}),
        "operations": operations,
        "caveat": "Response/error codes and DB/transaction/lock/shop semantics need manual code review and parity tests; OpenAPI is not proof of runtime behavior.",
    }
    CONTRACT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = [
        "# PHP migration API contract — reference inventory",
        "",
        f"Generated from **{len(operations)} registered FastAPI method/path routes**. The machine-readable inventory is [php-migration-api-contract.json](php-migration-api-contract.json).",
        "",
        "This is an inventory, **not PHP parity**. OpenAPI supplies declared request/response schemas, parameters, validation constraints, and status codes; registered dependency closures supply permission candidates. Service-level database operations, locking, exact transaction boundaries, error cases, and shop scoping remain `REVIEW_REQUIRED` per operation until manually traced and tested. Do not infer safety from a SALES allowlisted path alone.",
        "",
        "The PHP API must retain `/api/v1`, the `{message,error:{code,request_id}}` error envelope, current success envelopes, bearer/refresh semantics, authorization and assigned-store checks. See [sales endpoint permission matrix](../output/sales-endpoint-permission-matrix.md) and Phase 3 tests for known security boundaries.",
        "",
        "| Method | Path | Auth dependency values | SALES policy | Source | PHP status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in operations:
        auth = ", ".join(
            f"{dep.get('combination', dep['dependency'])}:" + (",".join(dep.get("required_values", [])) or "review")
            for dep in item["authorization_dependencies"]
        ) or "public/other — review"
        lines.append(f"| {item['method']} | `{item['path']}` | {auth} | {item['sales_route_policy']} | `{item['source']['file']}:{item['source']['line']}` | {item['php_parity_status']} |")
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"registered_method_paths={len(operations)} contract_json={CONTRACT_PATH.name}")


if __name__ == "__main__":
    main()
