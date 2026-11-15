import ast
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot")
sys.path.insert(0, os.path.join(ROOT, "core"))

import i18n  # noqa: E402

STOP = set(
    "de la el en que no se con para por un una los las del al es tu ya lo su sus más como esta este esto está están "
    "hay ha han fue ser sin sobre entre muy también cuando donde desde hasta pero sí nuevo nueva todo todos toda "
    "todas puede pueden tienes tiene ahora aquí cola buscar archivos archivo carpeta carpetas volver cancelar "
    "eliminar activar desactivar guardar añadir quitar probar usuario usuarios ajustes cuenta enlace enlaces "
    "descarga descargas pausa pausar reanudar historial limpiar página siguiente anterior cerrar aceptar abrir "
    "conectar desconectar cargar nombre ruta contraseña clave código teléfono canal idioma".split()
)
ALLOW = {
    "No",
    "No space",
    "Deluge Web UI has no daemon connection configured.",
    "🇪🇸 Español",
    "no-store, no-cache, must-revalidate, max-age=0",
    "✖️ No",
    "No results returned",
    "Elige el idioma de toda la interfaz (chat y web app).",
}
EXCLUDE = {"core/guides.py", "core/i18n.py"}
TAG = re.compile(r"<[^>]*>")
SQL = re.compile(r"\b(SELECT|INSERT|CREATE TABLE|CREATE INDEX|DELETE FROM|UPDATE|ALTER TABLE|PRAGMA)\b")


ACCENTS = r"[áéíóúñÁÉÍÓÚÑ¿¡]"
CODE_CHARS = re.compile(r"[\\^|]|://|\?q=|;q=|^[\w.-]+:$|[a-z]:[a-z]")


def looks_like_text(seg: str) -> bool:
    if CODE_CHARS.search(seg) or seg.startswith(("http", "/", ".", "%", "-")):
        return False
    if " " not in seg:
        if re.search(r"[_:/,]", seg):
            return False
        return seg[0].isupper() or bool(re.search(ACCENTS, seg))
    return True


def spanish(text: str) -> bool:
    if re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", text):
        return True
    return any(w in STOP for w in re.findall(r"[a-záéíóúñ]+", text.lower()))


class Collector(ast.NodeVisitor):
    def __init__(self):
        self.skip = set()
        self.found = []

    def visit_Call(self, node):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name in ("L", "debug", "info", "warning", "error", "exception", "critical"):
            for arg in node.args:
                for sub in ast.walk(arg):
                    self.skip.add(id(sub))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and id(node) not in self.skip:
            self.found.append(node.value)


def segments(value: str):
    if SQL.search(value):
        return
    for part in TAG.split(value):
        for line in part.split("\n"):
            seg = line.strip().strip("`").strip()
            if seg and re.search(r"[^\W\d_]", seg):
                yield seg


def test_no_untranslated_spanish():
    i18n.set_lang("en")
    missing = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True)):
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        if rel in EXCLUDE:
            continue
        collector = Collector()
        tree = ast.parse(open(path, encoding="utf-8").read())
        collector.visit(tree)
        for value in collector.found:
            for seg in segments(value):
                if seg in ALLOW or not looks_like_text(seg) or not spanish(seg):
                    continue
                out = i18n.tr(seg)
                if out == seg or re.search(ACCENTS, out):
                    missing.setdefault(seg, rel)
    assert not missing, "\n".join(f"{rel}: {seg!r}" for seg, rel in sorted(missing.items(), key=lambda x: x[1]))


if __name__ == "__main__":
    try:
        test_no_untranslated_spanish()
        print("OK")
    except AssertionError as e:
        print(e)
        sys.exit(1)
