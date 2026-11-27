# Simple WoltLab Plugin Manager

- Generisches Werkzeug für WoltLab-Pakete; keine produktabhängige Build-/Prüflogik ergänzen. Bestehende `.cursor/rules/` beachten.
- Einstieg: `README.de.md`, `tools/README.de.md`, `docs/HANDOFF.md`, für Details `tools/docs/`.
- Vor Änderungen `git status --short --branch` lesen. Vorhandene lokale Änderungen und ungesichtete Commits erhalten.
- Paketidentität, Anwendung, Abhängigkeiten und Zielversion aus dem Nutzerpaket ableiten. Bei Familien explizites Manifest verwenden.
- Aktuelle Erweiterungsarbeit betrifft WoltLab 6.3 als Entwicklungsziel; andere unterstützte Zielversionen des Managers nicht pauschal entfernen.
- Referenzen nur mit explizitem Branch und protokolliertem Commit verwenden. GitHub-Default ist nicht verlässlich die gewünschte Suite-Linie.
- `update-woltlab-version.sh --check --refs-only VERSION` prüft lesend; ohne `--check` werden saubere Referenzen auf explizite Commits synchronisiert. Lokale Änderungen/Commits nicht umgehen oder zurücksetzen.
- `woltlab-*`-Referenzcheckouts sind eigene Repositories und keine Manager-Quelldateien. Lokale Änderungen nicht verwerfen.
- `bash tools/tests/run-tests.sh` ist der bestehende lokale Testeinstieg. Bei Werkzeugänderungen sinnvolle Regressionstests ergänzen; bei Bash zusätzlich `bash -n` und, soweit verfügbar, Shellcheck.
- 6.3-Unterstützung nur mit konkreten Prüfungen belegen; Syntaxprüfung ist keine API-/Installationsprüfung. Release-ZIP, Git-Entwicklungsstand und Testbuild auseinanderhalten.
- Das eigene Recovery-Werkzeug liegt im eigenständigen Nachbarrepository `../sc-woltlab-plugin-recovery/`: dort `AGENTS.md` und `dev/HANDOFF.md` lesen. SWPM besitzt dessen Quellen nicht mehr; Build/Publisher/Deploy sind keine lesenden Checks.
- Keine `.env`, Zugangsdaten, lokalen Suite-Dateien, Cache-/Auth-Daten oder fremden Repositories committen.
- Geprüfte Änderungen in überschaubaren Commits sichern; keine ungesichteten Altstände pauschal pushen. Veröffentlichung ist ein eigener Schritt.
- Handoff nach Änderungen aktualisieren: Problem, Änderung, Tests, Grenzen, nächster Schritt.
