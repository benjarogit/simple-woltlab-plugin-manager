# Versionsgerechte WoltLab-Referenzen

SWPM bleibt für Einzelpakete, Apps und beliebige Paketfamilien nutzbar. Die Zielversion stammt aus der WCF-Abhängigkeit des Pakets; ein Familienmanifest wird ausdrücklich ausgewählt. Ein vorhandener Download oder der neueste GitHub-Branch bestimmt die Zielversion nicht.

Vom SWPM-Repository aus:

```bash
# Lesend: die ausdrücklich gewählte Entwicklungslinie prüfen.
./tools/update-woltlab-version.sh --check --refs-only 6.3

# Schreibend: saubere Referenzen dieser Linie separat synchronisieren.
./tools/update-woltlab-version.sh --refs-only 6.3

# Ein anderes Paket anhand seiner eigenen WCF-Abhängigkeit prüfen.
./tools/update-woltlab-version.sh --check --refs-only --package /pfad/zum/paket
```

Die Linien liegen getrennt unter `.references/X.Y/`. `WOLTLAB_REFERENCES_ROOT` bezeichnet bei Bedarf genau einen Linienbestand, nicht dessen übergeordnetes Verzeichnis. Bestehende Referenzen im Manager-Hauptverzeichnis bleiben erhalten und werden nicht automatisch migriert. Sie sind ausdrücklich mit `--legacy-root --check` lesend prüfbar beziehungsweise über den expliziten Root auswählbar.

Jeder Git-Bestand protokolliert Herkunft, Branch und Commit in `reference-lock.json`. Core-Releasearchive haben eine eigene Versions-/Hashprovenienz. Eine Git-Entwicklungslinie ist kein verfügbares stabiles Release-ZIP: `--refs-only` lädt keines. Fehlende Linien, abweichende Pins, lokale Änderungen und inkompatible Core-Versionen führen zu einem Fehler; es gibt keinen Rückgriff auf die neueste andere Linie.

Build und Validierung verwenden die Paketkompatibilität und prüfen den gewählten Core sowie die Typdefinitionen. Für einen ausdrücklich ausgewählten Bestand:

```bash
WOLTLAB_REFERENCES_ROOT=/pfad/zu/SWPM/.references/6.3 \
  ./tools/build.sh /pfad/zum/paket same
```

Ein abweichender `WOLTLAB_CORE_REFERENCE` muss dieselbe kompatible Linie erfüllen. TypeScript-Pfade werden nicht stillschweigend umgeschrieben. Der Prüfer benötigt derzeit eine JSON-Konfiguration mit unmittelbar angegebenen Compilerpfaden; geerbte `tsconfig`-Konfigurationen werden mit Fehler abgewiesen und müssen ausdrücklich als aufgelöste Eingaben bereitgestellt werden. Das ist eine dokumentierte Einschränkung, keine bestandene TypeScript-Prüfung.

Referenzsynchronisation aktualisiert keine installierte Test-Suite. Quellenprüfung, Paketbau, Live-Abnahme und GitHub-CI bleiben getrennte Nachweise.

Verwaltete Referenzen müssen eigenständige Git-Checkouts mit eigenem Git-Verzeichnis innerhalb ihres Referenzpfads sein. Umgeleitete `core.worktree`-Pfade, geteilte Git-Verzeichnisse und verknüpfte Worktrees werden abgewiesen. Symbolische Links im Referenzpfad erfordern die ausdrücklich angegebene kanonische Zieladresse.
