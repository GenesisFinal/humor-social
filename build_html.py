"""
Compilador del sitio web estático para GitHub Pages.
Genera master_dataset.json y verifica los assets para publicación.
"""

from pathlib import Path
from build_dataset import build_dataset

def build():
    print("=== COMPILANDO SITIO WEB PARA GITHUB PAGES ===")
    json_path = build_dataset()
    index_path = Path(__file__).resolve().parent / "index.html"
    
    if not index_path.exists():
        raise FileNotFoundError("No se encontró index.html en la raíz del proyecto.")

    print(f"[OK] index.html verificado ({index_path.stat().st_size} bytes)")
    print(f"[OK] master_dataset.json verificado ({json_path.stat().st_size} bytes)")
    print("=== COMPILACIÓN COMPLETADA EXITOSAMENTE ===")

if __name__ == "__main__":
    build()
