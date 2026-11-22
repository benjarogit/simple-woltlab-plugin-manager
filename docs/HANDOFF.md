# Übergabe: SWPM – sichere Referenzen und Paketfamilien

## Getrennte Referenzlinien und eigenständiges Recovery – 22. November 2026

SWPM bleibt allgemeines Werkzeug für Einzelplugins, Apps und beliebige Paketfamilien. Die Zielversion wird ausdrücklich aus Paket-/WCF-Kompatibilität und gegebenenfalls ausgewähltem Familienmanifest bestimmt. Keine stillschweigende neueste Linie, kein Rückgriff auf fremde Core-/Typdefinitionen. Referenzen liegen getrennt unter `.references/X.Y/`; explizite alte Roots bleiben auswählbar. Herkunft, Branch, Commit und Core-Archivhash werden protokolliert. JSON-tsconfig mit direkten Compilerpfaden erforderlich; geerbte Konfigurationen werden mit Fehler abgewiesen. Verwaltete Referenzen erfordern eigenständige Git-Checkouts ohne umgeleitete oder geteilte Metadaten.

Unabhängig reproduzierte Grenzfehler wurden gezielt korrigiert: Referenzpfad-Vorfahren, native TypeScript-Wildcard-Aliase, umgeleitete Git-Arbeitsverzeichnisse/Metadaten und die vom Updater abweichende Statusanzeige. Tatsächliche finale lokale Prüfungen: **171 Python-Tests und sieben Shellprüfungen** am vollständigen vorhandenen Arbeitsbaum. Davon getrennt: **61 Python-Tests und sieben Shellprüfungen** am selektiven Commit-Kandidaten. Frühere PIP-/AMD-/Familienänderungen wurden nicht pauschal in diesen Kandidaten aufgenommen. Keine Behauptung eines vollständigen Shellcheck-, PHPStan-, Windows-, Store- oder Live-PASS.

Die sechs offiziellen 6.3-Git-Referenzen wurden separat synchronisiert. Vorhandene aktive Git-Referenzen, Lockdatei und Core6.2.6-Download blieben unverändert; alte Provenienz vorher gesichert. Kein neuer stabiler Core-ZIP-Download und keine Änderung an Benjaros installiertem Oktober-Core. Portable Provenienz: `docs/REFERENCE-UPDATE-20261122.json`; Anleitung und Grenzen: `tools/docs/VERSIONED-REFERENCES.de.md` und `.en.md`.

Das eigene Recovery gehört vollständig ins eigenständige Repository `sc-woltlab-plugin-recovery`. Ursprüngliche öffentliche Historie und relevante SWPM-Quellenhistorie erhalten; 53 Ausgangsdateien hashgenau importiert. Geprüfter Entwicklungscommit `6488cc7` normal gepusht, Draft-PR1 im Recovery-Repository. Eigenständige13 Offline-Regressionen, Syntax, Build und rein planender Publisher geprüft; kein automatischer Commit/Tag/Push/Release. Die alte SWPM-Kopie erst nach Quellen-/Historienvergleich und eigenständiger Prüfung reversibel archiviert. WSC Lokals offizielles Recovery bleibt separat; keine Live-Reparatur vorgenommen.

Entwicklungsbranch `codex/versioned-workspace-20261122`. Quellen, selektiver Index, vollständiger lokaler Arbeitsbaum, GitHub-CI und externe Reviews bleiben getrennte Nachweise. Übrige ältere uncommittierte Manager-Arbeiten erhalten und privat gesichert; nicht als fertig mitveröffentlicht. Kein Merge in main, kein Force-Push und kein Release. Nächster Schritt: allgemeine noch uncommittierte Prüfwerkzeuge einzeln auf Abhängigkeiten und Publikationsreife prüfen; SHR1NKR-spezifische Logik bleibt ausschließlich im Familienrepository.

Die folgenden Einträge sind historische Zwischenstände.

Stand: 13. November 2026. Manager bleibt generisch; die aktuelle Zielerweiterung betrifft WoltLab 6.3 als Entwicklungsstand, keine pauschale Release-Freigabe.

## Änderungen dieser Runde

- `sync-woltlab-git.py`: explizite Branches, lesender Status ohne Git-Fetch/Checkout/Cache-Dateien, Schutz schmutziger Quellen und lokaler Commits, keine Hard-Resets oder Löschung fremder Verzeichnisse, Fehlerstatus bei fehlenden Branches/Teilfehlern, Commit-Protokoll. Acht lokale Git-Fixture-Regressionstests.
- `update-woltlab-version.sh`: expliziter `--check` bleibt lesend, Git-Referenzen und stabile Core-ZIPs getrennt. `--refs-only 6.3` setzt keinen offiziellen 6.3-Download voraus. `sync-woltlab-references.sh` nutzt die konfigurierte Linie statt fest 6.2.
- Validator löst die Mindestversion von `com.woltlab.wcf` XML-basiert auf, unabhängig von Reihenfolge/Anführungszeichen der Abhängigkeiten. 6.3 wird erkannt, aber nicht als automatisch releasefähig bewertet.
- TypeScript-Build erhält das tatsächlich gewählte Plugin explizit; kein zufälliger erster Build-Slot. Regressionstest mit zwei Paketen.
- ACP-Assetprüfung berücksichtigt von WCF gelieferte Dateien über `WOLTLAB_CORE_REFERENCE`/`WOLTLAB_ROOT` sowie ausdrücklich erforderliche Familienpakete über `SWPM_FAMILY_MANIFEST`. Optionale Siblings gelten nicht als garantierte Ressourcen. Familien-Pipeline reicht Manifest weiter.
- Page-Options-Prüfung betrachtet nur den tatsächlichen `checkModules`-Methodenrumpf, auch bei Rückgabetyp und verschachtelten Klammern. Darstellungs-/Timing-Konstanten anderer Methoden sind keine Zugriffssperren.
- Fehlerhaftes console.log-grep und unnötige `com.`-Beschränkung bei Paketnamen korrigiert. Generischer CLI-Installationshelfer unterstützt expliziten Host und moderne authentifizierte WCF-Sessioncookies; keine Zugangsdaten im Quellcode.

## Referenzstand und lokale Arbeit

Sechs offizielle Referenzprojekte stehen lokal auf 6.3-Commits. Ursprüngliche 6.2-Bäume samt lokaler Änderungen sind unter `.references/6.2-preserved/` erhalten. Aktive SHAs stehen lokal in `reference-lock.json`; `tools/.env` wählt lokal Linie 6.3. Beides sind lokale Arbeitsdaten, keine Veröffentlichung von WoltLab-Quellen.

Vorhandene fremde Änderungen bleiben erhalten. Insbesondere Audit-/Installationsreste, produktspezifische Einmalhelfer sowie weitere ungesichtete Prüfer/Dokumentänderungen nicht pauschal in diesen Commit aufnehmen. Tests und Registry nur für die hier bearbeiteten generischen Prüfungen aufnehmen; andere lokale Erweiterungen getrennt halten.

## Prüfungen

Lokaler Testeinstieg: `bash tools/tests/run-tests.sh`. Neue/angepasste Testfälle umfassen sicheren Git-Sync, XML-Abhängigkeitsauflösung, explizite TS-Auswahl, WCF-/Pflichtabhängigkeits-Assets und präzise Options-Gates. Python-Tests, Bash-Syntax und Shellcheck der neuen Sync-/Wrapperpfade erfolgreich. Gesamte Produktfamilie konnte über die bearbeitete Pipeline gebaut werden. Das ist keine vollständige API-/Browser-/Store-Abnahme.

Bekannte Grenze: Validator durchsucht noch Entwicklungsbäume/node_modules und erzeugt dadurch irreführende Debug-/Cloud-Warnungen. Quell- und ausgelieferten Paketumfang künftig klarer trennen. Syntaxprüfung erkennt keine PHP-8.5-Laufzeit-Deprecations; passende Browser-/Laufzeittests bleiben erforderlich.

Der Recovery-Werkzeugbereich behält sein eigenes `dev/HANDOFF.md`; weder neue Recovery-Veröffentlichung noch destruktive Recovery-Tests dieser Runde.
