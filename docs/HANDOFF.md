# Übergabe: SWPM – sichere Referenzen und Paketfamilien

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
