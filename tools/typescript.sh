#!/usr/bin/env bash

#################################################################
# WoltLab TypeScript Build-Skript
# Kompiliert TypeScript → JavaScript
# Entfernt alte d3.js/TopoJSON Dateien (nicht mehr benötigt, ersetzt durch flot.js)
#
# Usage:
#   ./tools/typescript.sh        → Kompiliert TypeScript
#   ./tools/typescript.sh watch   → Watch-Mode (automatische Kompilierung)
#
# Das Script sucht automatisch nach temp_edit/ Verzeichnissen
# in allen Plugin-Verzeichnissen im Projekt-Root
#################################################################

set -e

#=====================================
# KONFIGURATION
#=====================================
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MAIN_DIR="$(dirname "$SCRIPT_DIR")"

#=====================================
# QUELLEN
#=====================================
if [ -f "$SCRIPT_DIR/common.sh" ]; then
    source "$SCRIPT_DIR/common.sh"
else
    # Fallback-Farben
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m'
    
    print_section() {
        local title="$1"
        echo -e "${CYAN}==========================================${NC}"
        echo -e "${CYAN}${title}${NC}"
        echo -e "${CYAN}==========================================${NC}"
        echo ""
    }
    
    print_success() { echo -e "${GREEN}✓ $1${NC}"; }
    print_error() { echo -e "${RED}✗ $1${NC}"; }
    print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
    print_info() { echo -e "${CYAN}ℹ $1${NC}"; }
fi

#=====================================
# HAUPTLOGIK
#=====================================
TEMP_EDIT_DIR=""
WATCH_MODE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --plugin)
            if [ $# -lt 2 ]; then echo "--plugin requires a directory" >&2; exit 1; fi
            TEMP_EDIT_DIR="$2"; shift 2 ;;
        watch) WATCH_MODE="watch"; shift ;;
        *) echo "Usage: $0 [--plugin DIRECTORY] [watch]" >&2; exit 1 ;;
    esac
done
if [ -n "$TEMP_EDIT_DIR" ]; then
    if [ -d "$TEMP_EDIT_DIR/temp_edit" ]; then TEMP_EDIT_DIR="$TEMP_EDIT_DIR/temp_edit"; fi
    if [ ! -f "$TEMP_EDIT_DIR/package.json" ]; then
        echo "Explicit plugin has no package.json: $TEMP_EDIT_DIR" >&2; exit 1
    fi
    TEMP_EDIT_DIR="$(cd "$TEMP_EDIT_DIR" && pwd)"
else
    for plugin_dir in "${MAIN_DIR}"/*; do
        if [ -d "$plugin_dir/temp_edit" ] && [ -f "$plugin_dir/temp_edit/package.json" ]; then
            TEMP_EDIT_DIR="$(cd "$plugin_dir/temp_edit" && pwd)"; break
        fi
    done
fi

if [ -z "$TEMP_EDIT_DIR" ]; then
    print_error "Kein temp_edit Verzeichnis mit package.json gefunden"
    print_warning "Suche in: ${MAIN_DIR}/*/temp_edit/"
    exit 1
fi

cd "${TEMP_EDIT_DIR}"

# Parameter parsen


# Header anzeigen
if [ "$WATCH_MODE" = "watch" ]; then
    print_section "WoltLab TypeScript Build - Watch-Mode" "Hauptmenü" "Build"
else
    print_section "WoltLab TypeScript Build" "Hauptmenü" "Build"
fi

print_info "Verzeichnis: ${TEMP_EDIT_DIR}"
# Optional: Hinweis, wenn WoltLab d.ts fehlt (für typeRoots in tsconfig.json)
ENV_FILE="$SCRIPT_DIR/.env"
DTS_DIR=""
if [ -f "$ENV_FILE" ]; then
    DTS_DIR=$(grep -E "^WOLTLAB_DTS_DIR=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '\r\n' || true)
fi
[ -z "$DTS_DIR" ] && DTS_DIR="woltlab-d-ts"
if [ ! -d "$MAIN_DIR/$DTS_DIR" ] || [ ! -f "$MAIN_DIR/$DTS_DIR/.git/HEAD" ]; then
    print_warning "WoltLab d.ts nicht gefunden (${DTS_DIR}). Für Typings: Setup ausführen (d.ts klonen). Siehe tools/README.md."
fi
echo ""

# Prüfe ob package.json existiert
if [ ! -f "package.json" ]; then
    print_error "package.json nicht gefunden in temp_edit/"
    print_warning "Bitte erstelle zuerst package.json"
    exit 1
fi

# Prüfe ob tsconfig.json existiert
if [ ! -f "tsconfig.json" ]; then
    print_error "tsconfig.json nicht gefunden in temp_edit/"
    print_warning "Bitte erstelle zuerst tsconfig.json"
    exit 1
fi

# npm install, falls node_modules fehlt
if [ ! -d "node_modules" ]; then
    print_info "[1/4] npm install..."
    npm install
    print_success "npm install abgeschlossen"
    echo ""
else
    print_success "node_modules vorhanden"
    echo ""
fi

# Prüfe ob TypeScript-Dateien existieren
TS_COUNT=0
if [ -d "ts" ]; then
    TS_COUNT=$(find ts -name "*.ts" 2>/dev/null | wc -l)
fi

if [ "$TS_COUNT" -eq 0 ]; then
    print_warning "Keine TypeScript-Dateien gefunden in ts/"
    print_warning "Überspringe Kompilierung"
    echo ""
else
    print_info "[2/4] TypeScript kompilieren..."
    print_info "${TS_COUNT} TypeScript-Dateien gefunden"
    
    # TypeScript kompilieren
    run_tsc() {
        if command -v npx &> /dev/null; then
            npx tsc "$@"
        elif [ -f "node_modules/typescript/bin/tsc" ]; then
            node node_modules/typescript/bin/tsc "$@"
        else
            print_error "weder npx noch node_modules/typescript/bin/tsc gefunden"
            exit 1
        fi
    }

    if command -v npx &> /dev/null || [ -f "node_modules/typescript/bin/tsc" ]; then
        if [ "$WATCH_MODE" = "watch" ]; then
            print_info "Watch-Mode: TypeScript kompiliert automatisch bei Änderungen"
            print_info "Drücke Ctrl+C zum Beenden"
            echo ""
            run_tsc -w
        else
            # WICHTIG: Lösche alle .js und .min.js Dateien, die aus .ts Dateien kompiliert werden
            # Dies stellt sicher, dass TypeScript IMMER neu kompiliert, auch wenn .js Dateien neuer sind
            # Außerdem werden verwaiste .min.js Dateien entfernt (wenn .ts Datei gelöscht wurde)
            print_info "Lösche alte .js und .min.js Dateien für saubere Kompilierung..."
            if [ -d "js" ]; then
                # Finde alle .ts Dateien und lösche die entsprechenden .js und .min.js Dateien
                mapfile -t ts_files < <(find ts -name "*.ts" -type f 2>/dev/null)
                DELETED_JS_COUNT=0
                DELETED_MIN_COUNT=0
                for ts_file in "${ts_files[@]}"; do
                    # Konvertiere ts/.../file.ts zu js/.../file.js
                    js_file="${ts_file#ts/}"
                    js_file="${js_file%.ts}.js"
                    js_path="js/${js_file}"
                    min_path="js/${js_file%.js}.min.js"
                    
                    # Lösche .js Datei, falls sie existiert
                    if [ -f "$js_path" ]; then
                        rm -f "$js_path"
                        DELETED_JS_COUNT=$((DELETED_JS_COUNT + 1))
                    fi
                    
                    # Lösche .min.js Datei, falls sie existiert
                    if [ -f "$min_path" ]; then
                        rm -f "$min_path"
                        DELETED_MIN_COUNT=$((DELETED_MIN_COUNT + 1))
                    fi
                done
                
                if [ "$DELETED_JS_COUNT" -gt 0 ] || [ "$DELETED_MIN_COUNT" -gt 0 ]; then
                    print_success "${DELETED_JS_COUNT} .js Datei(en) und ${DELETED_MIN_COUNT} .min.js Datei(en) gelöscht"
                else
                    print_success "Keine alten Dateien zu löschen"
                fi
            fi
            
            # Jetzt kompilieren (TypeScript wird alle .js Dateien neu erstellen)
            # WICHTIG: Da wir alle .js Dateien gelöscht haben, wird TypeScript IMMER neu kompilieren
            # Zusätzlich: Lösche TypeScript Cache falls vorhanden, um sicherzustellen dass alles frisch ist
            if [ -d ".tsbuildinfo" ]; then
                rm -rf .tsbuildinfo
            fi
            run_tsc
            TSC_EXIT=$?
            if [ $TSC_EXIT -eq 0 ]; then
                print_success "TypeScript kompiliert"
                
                # Validierung: Prüfe ob JavaScript-Dateien erstellt wurden
                JS_COUNT=0
                if [ -d "js" ]; then
                    # WICHTIG: Zähle nur .js Dateien, NICHT .min.js!
                    JS_COUNT=$(find js -name "*.js" ! -name "*.min.js" 2>/dev/null | wc -l)
                fi
                
                if [ "$TS_COUNT" -gt 0 ] && [ "$JS_COUNT" -eq 0 ]; then
                    print_error "TypeScript-Dateien gefunden, aber keine JavaScript-Dateien erstellt!"
                    print_error "Kompilierung scheint fehlgeschlagen zu sein."
                    exit 1
                fi
                
                print_success "Validierung: ${TS_COUNT} TypeScript → ${JS_COUNT} JavaScript Dateien"
                
                # Eine .min.js braucht nur, was per {js file='X'} eingebunden wird: bei
                # ENABLE_DEBUG_MODE=0 haengt JsFunctionTemplatePlugin .min an und fragt
                # X.min.js an. Solche Dateien liegen direkt in js/.
                # Module in Unterordnern laedt RequireJS ueber ihre Modul-ID immer als .js,
                # eine .min.js dort wird nie angefragt. WoltLab minifiziert dort auch nicht
                # pro Modul, sondern buendelt alle Module (extra/_buildExternal.js).
                print_info "Prüfe .min.js Dateien für {js}-Einbindungen in js/..."
                MIN_JS_COUNT=0
                if [ -d "js" ]; then
                    mapfile -t jsfiles < <(find js -maxdepth 1 -name "*.js" ! -name "*.min.js" -type f)
                    for jsfile in "${jsfiles[@]}"; do
                        minfile="${jsfile%.js}.min.js"
                        # eine echt minifizierte Datei nicht durch eine Kopie ersetzen
                        if [ -f "$minfile" ] && ! diff -q "$jsfile" "$minfile" > /dev/null 2>&1; then
                            print_info "$(basename "$minfile") ist minifiziert und bleibt unverändert"
                            continue
                        fi
                        if ! cp -f "$jsfile" "$minfile"; then
                            print_error "Fehler beim Kopieren: $jsfile → $minfile"
                            exit 1
                        fi
                        MIN_JS_COUNT=$((MIN_JS_COUNT + 1))
                    done

                    mapfile -t stale_minfiles < <(find js -mindepth 2 -name "*.min.js" ! -path "*/3rdParty/*" -type f)
                    if [ ${#stale_minfiles[@]} -gt 0 ]; then
                        print_warning "${#stale_minfiles[@]} .min.js Datei(en) in Modul-Ordnern; RequireJS fragt sie nie an:"
                        for stale in "${stale_minfiles[@]}"; do
                            echo -e "   - ${YELLOW}${stale}${NC}"
                        done
                    fi
                fi

                if [ "$MIN_JS_COUNT" -gt 0 ]; then
                    print_success "${MIN_JS_COUNT} .min.js Datei(en) aus js/ aktualisiert"
                else
                    print_success "Keine .min.js Datei nötig"
                fi
                echo ""
            else
                print_error "TypeScript-Kompilierung fehlgeschlagen!"
                exit 1
            fi
        fi
    else
        print_error "npx nicht gefunden!"
        print_error "Installiere Node.js und npm"
        exit 1
    fi
fi

# D3.js und TopoJSON werden nicht mehr benötigt (ersetzt durch flot.js)
# Die Dateien werden nicht mehr automatisch kopiert
# Falls sie noch vorhanden sind, werden sie beim nächsten Build entfernt
if [ -d "js/3rdParty/d3" ]; then
    print_info "[3/4] Entferne alte d3.js Dateien (nicht mehr benötigt)..."
    rm -rf js/3rdParty/d3
    print_success "d3.js Verzeichnis entfernt"
    echo ""
fi

if [ -d "js/3rdParty/topojson-client" ]; then
    print_info "[4/4] Entferne alte TopoJSON Dateien (nicht mehr benötigt)..."
    rm -rf js/3rdParty/topojson-client
    print_success "TopoJSON Verzeichnis entfernt"
    echo ""
fi

if [ "$WATCH_MODE" != "watch" ]; then
    echo ""
    print_section "Build abgeschlossen" "Hauptmenü" "Build"
    print_success "TypeScript Build abgeschlossen!"
    echo ""
    print_info "Nächste Schritte:"
    TOOLS_BUILD="$(cd "${SCRIPT_DIR}" && pwd)/build.sh"
    echo -e "  1. ${GREEN}${TOOLS_BUILD}${NC} ausführen (erstellt Plugin-Paket)"
    echo -e "  2. Plugin im ACP installieren"
    echo ""
fi
