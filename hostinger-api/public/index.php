<?php
declare(strict_types=1);

use Anicraze\Http\Application;
use Anicraze\Config\Environment;

require dirname(__DIR__) . '/vendor/autoload.php';
Environment::load(dirname(__DIR__));

(new Application())->run();
