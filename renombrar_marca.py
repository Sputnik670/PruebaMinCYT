import os

# Configuración
CARPETA_OBJETIVO = './frontend_dashboard'
TEXTO_ORIGINAL = 'MinCYT'
TEXTO_NUEVO = 'SICyT'
EXTENSIONES_PERMITIDAS = ('.tsx', '.ts', '.js', '.html', '.css', '.json', '.md')

def reemplazar_texto_en_archivos():
    contador = 0
    print(f"🔄 Iniciando reemplazo de '{TEXTO_ORIGINAL}' a '{TEXTO_NUEVO}' en {CARPETA_OBJETIVO}...")
    
    for root, dirs, files in os.walk(CARPETA_OBJETIVO):
        # Ignorar carpeta node_modules para no romper librerías
        if 'node_modules' in dirs:
            dirs.remove('node_modules')
            
        for file in files:
            if file.endswith(EXTENSIONES_PERMITIDAS):
                ruta_archivo = os.path.join(root, file)
                
                try:
                    with open(ruta_archivo, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    if TEXTO_ORIGINAL in contenido:
                        nuevo_contenido = contenido.replace(TEXTO_ORIGINAL, TEXTO_NUEVO)
                        
                        with open(ruta_archivo, 'w', encoding='utf-8') as f:
                            f.write(nuevo_contenido)
                        
                        print(f"✅ Modificado: {ruta_archivo}")
                        contador += 1
                except Exception as e:
                    print(f"⚠️ No se pudo leer/escribir {ruta_archivo}: {e}")

    print(f"\n🎉 ¡Listo! Se actualizaron {contador} archivos.")
    print("👉 Nota: Si tenías variables de entorno o nombres de carpetas con 'MinCYT', revísalos manualmente.")

if __name__ == "__main__":
    reemplazar_texto_en_archivos()