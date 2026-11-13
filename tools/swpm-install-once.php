#!/usr/bin/env php
<?php

/**
 * Container DEV helper: install/update one package non-interactively.
 * Usage: WCF_SESSION_ID=… php /tmp/swpm-install-once.php /path/to/pkg.tar.gz
 */

if (\PHP_SAPI !== 'cli') {
    exit(1);
}

$archivePath = $argv[1] ?? '';
if ($archivePath === '' || !\is_readable($archivePath)) {
    \fwrite(\STDERR, "Usage: WCF_SESSION_ID=<session> php swpm-install-once.php <package.tar.gz>\n");
    exit(1);
}

// CLI has no HTTP request context; application bootstrap / domain helpers need a host.
if (!\getenv('HTTP_HOST')) { \fwrite(\STDERR, "HTTP_HOST is required for the explicit target\n"); exit(1); }
$_SERVER['HTTP_HOST'] ??= \getenv('HTTP_HOST');
$_SERVER['HTTPS'] ??= \getenv('HTTPS') ?: 'on';
$_SERVER['SERVER_PORT'] ??= \getenv('SERVER_PORT') ?: '443';
$_SERVER['REQUEST_URI'] ??= '/';
$_SERVER['REMOTE_ADDR'] ??= '127.0.0.1';

\define('PACKAGE_ID', 1);
\define('ENABLE_BENCHMARK', 0);

require_once (\getenv('WCF_ROOT') ?: '/var/www/html') . '/app.config.inc.php';
if (\getenv('WCF_SESSION_COOKIE_NAME') && \getenv('WCF_SESSION_COOKIE_VALUE')) {
    $_COOKIE[\getenv('WCF_SESSION_COOKIE_NAME')] = \getenv('WCF_SESSION_COOKIE_VALUE');
}
require_once WCF_DIR . 'lib/system/WCF.class.php';

use wcf\data\package\installation\queue\PackageInstallationQueue;
use wcf\data\package\installation\queue\PackageInstallationQueueEditor;
use wcf\data\package\Package;
use wcf\data\session\SessionEditor;
use wcf\system\package\PackageInstallationDispatcher;
use wcf\system\package\validation\PackageValidationManager;
use wcf\system\WCF;
use wcf\util\FileUtil;

final class SwpmInstallBootstrap extends WCF
{
    public function __construct()
    {
        if (!\defined('TMP_DIR')) {
            \define('TMP_DIR', FileUtil::getTempFolder());
        }
        $this->initDB();
        $this->loadOptions();
        $this->initSession();
        $this->initLanguage();
        $this->initTPL();
        $this->initCoreObjects();
        $this->initApplications();
        $this->runBootstrappers();
    }

    protected function initSession(): void
    {
        parent::initSession();
        if (\getenv('WCF_SESSION_COOKIE_VALUE')) {
            if (WCF::getUser()->isGuest()) {
                \fwrite(\STDERR, "Invalid authenticated session cookie\n");
                exit(1);
            }
            return;
        }
        if (empty($_ENV['WCF_SESSION_ID'])) {
            \fwrite(\STDERR, "WCF_SESSION_ID required\n");
            exit(1);
        }
        WCF::getSession()->delete();
        WCF::getSession()->load(SessionEditor::class, $_ENV['WCF_SESSION_ID']);
        if (!WCF::getUser()->userID) {
            \fwrite(\STDERR, "Invalid WCF_SESSION_ID\n");
            exit(1);
        }
    }
}

new SwpmInstallBootstrap();

// Application installs prompt for packageDir in ACP; for CLI use the default path under WCF_DIR.
WCF::getSession()->register('__wcfSetup_developerMode', true);
\putenv('WCFSETUP_USEDEFAULTWCFDIR=1');
$_ENV['WCFSETUP_USEDEFAULTWCFDIR'] = '1';

$session = WCF::getSession();
if (
    !$session->getPermission('admin.configuration.package.canInstallPackage')
    && !$session->getPermission('admin.configuration.package.canUpdatePackage')
) {
    \fwrite(\STDERR, "No install/update permission\n");
    exit(1);
}

$tmpArchive = FileUtil::getTemporaryFilename(
    'package_',
    \preg_replace('!^.*(?=\.(?:tar\.gz|tgz|tar)$)!i', '', \basename($archivePath))
);

if (!@\copy($archivePath, $tmpArchive)) {
    \fwrite(\STDERR, "Failed to copy archive\n");
    exit(1);
}

if (!PackageValidationManager::getInstance()->validate($tmpArchive, false)) {
    \fwrite(\STDERR, "Package validation failed\n");
    exit(1);
}

$validationArchive = PackageValidationManager::getInstance()->getPackageValidationArchive();
$packageInfo = $validationArchive->getArchive()->getPackageInfo('name');
$packageName = $validationArchive->getArchive()->getLocalizedPackageInfo('packageName');
$isApplication = $validationArchive->getArchive()->getPackageInfo('isApplication');

$existingPackage = null;
$sql = 'SELECT * FROM wcf' . WCF_N . '_package WHERE package = ?';
$statement = WCF::getDB()->prepareStatement($sql);
$statement->execute([$packageInfo]);
$row = $statement->fetchArray();
if ($row) {
    $existingPackage = new Package(null, $row);
}

$action = $existingPackage !== null ? 'update' : 'install';
$processNo = PackageInstallationQueue::getNewProcessNo();

$queue = PackageInstallationQueueEditor::create([
    'processNo' => $processNo,
    'userID' => WCF::getUser()->userID,
    'package' => $packageInfo,
    'packageName' => $packageName,
    'packageID' => $existingPackage?->packageID,
    'archive' => $tmpArchive,
    'action' => $action,
    'isApplication' => $isApplication ? '1' : '0',
]);

$dispatcher = new PackageInstallationDispatcher($queue);
$dispatcher->updatePackage();
$dispatcher->nodeBuilder->purgeNodes();
$dispatcher->nodeBuilder->buildNodes();

$node = $dispatcher->nodeBuilder->getNextNode();
$steps = 0;
$packageProp = new \ReflectionProperty(PackageInstallationDispatcher::class, 'package');
while ($node !== '') {
    $step = $dispatcher->install($node);
    $node = $step->getNode();
    // ACP runs one HTTP request per node and reloads Package; CLI must drop the cache
    // or application packageDir prompts loop forever on the stale empty packageDir.
    $packageProp->setValue($dispatcher, null);
    $steps++;
    if ($steps > 10000) {
        \fwrite(\STDERR, "too many steps\n");
        exit(1);
    }
}

\fwrite(\STDOUT, "OK: {$action} {$packageInfo} ({$steps} steps)\n");
