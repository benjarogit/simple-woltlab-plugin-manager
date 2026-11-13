# Übergabe: Plugin Recovery

Stand: 13. November 2026. Bestandsaufnahme; kein Recovery-Lauf, Build oder Release dieser Runde.

## Zuständigkeit und Quellen

- Bearbeitbare Quellen: `stub/` und `recovery-src/`; Build-/Entwicklungshilfen: `dev/`; Ausgaben: `dist/`.
- Versionsverwaltung der Quellen erfolgt im übergeordneten Plugin-Manager-Repository. Dort sind bereits Quellen auf `origin/main` enthalten.
- [Eigenes öffentliches Repository](https://github.com/benjarogit/sc-woltlab-plugin-recovery), Branch `master`: zwei READMEs und auslieferbarer PHP-Stub. Release `v2.7.48` enthält Stub und Paketarchiv. Nicht als vollständigen Quellcheckout behandeln.
- WSC Lokals integriertes Recovery ist das offizielle WoltLab-Tool und ein anderes Produkt. Eine Kopplung des eigenen Tools ist noch nicht implementiert.

## Harness

`bash dev/validate-php-syntax.sh` besteht für Quellstub, Paketquellen und dist-Stub. Nur Syntax geprüft. Das Skript meldet bei fehlendem PHP derzeit Warnung und Exit 0; als verbindliches Gate künftig fehlende Prüfung deutlich behandeln.

Nach PHP-Änderungen lokale Regel `.cursor/rules/php-recovery-tool.mdc` und Syntaxgate beachten. Vor produktiver Reparatur erst Diagnose/Vorschau und Daten-/Dateisicherung. Reparatur und Deinstallation nur auf einem bewusst gewählten Ziel.

## Offene Punkte

- Noch keine Wiederherstellungsabnahme mit WoltLab 6.3/PHP 8.5. Gegen einen protokollierten Snapshot einer wegwerfbaren Testinstallation testen.
- Versionsquellen sind uneinheitlich: Quellmanifest 2.7.12; Quell-`version.php` Paket 2.7.48/Stub 2.7.15; Quellstub Paket 2.7.48/Stub 2.7.42. Der Build überschreibt Ausgabemetadaten. Das erklärt mögliche Unterschiede, ersetzt aber keinen Artefaktcheck.
- Regressionstests fehlen als klarer gemeinsamer Einstieg für Auth, Diagnose, Vorschau, Paketabhängigkeiten, Dateireparatur, Cache/ACP-Reparatur und vollständige Tool-Entfernung. Keine absichtlichen Beschädigungen an der normalen Entwicklerinstanz.
- `dev/publish-github-release.sh` baut, committet und pusht selbst und kann Release-Assets mit `--clobber` ersetzen. Nicht als Prüfskript ausführen; Veröffentlichung separat vorbereiten und prüfen.

Nächster Schritt: Versionsvertrag und reproduzierbare Build-Prüfung definieren, anschließend isolierte 6.3-Recovery-Szenarien. Die bloße Angabe „6.0+“ in der README belegt keine geprüfte 6.3-Wiederherstellung.
