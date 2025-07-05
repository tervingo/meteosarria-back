#!/usr/bin/env python3
"""
Script de verificación para despliegue en Render
Verifica que todos los componentes del sistema de caché estén listos
"""

import os
import sys
import importlib

def check_requirements():
    """Verifica que todas las dependencias estén instaladas"""
    print("🔍 Verificando dependencias...")
    
    required_packages = [
        'flask',
        'flask_cors', 
        'flask_caching',
        'pymongo',
        'pytz',
        'gunicorn'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NO INSTALADO")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Faltan dependencias: {', '.join(missing_packages)}")
        print("Ejecuta: pip install -r requirements.txt")
        return False
    
    print("✅ Todas las dependencias están instaladas")
    return True

def check_files():
    """Verifica que todos los archivos necesarios existan"""
    print("\n🔍 Verificando archivos...")
    
    required_files = [
        'app.py',
        'cache_manager.py',
        'api_historico.py',
        'production_config.py',
        'requirements.txt',
        'Dockerfile',
        'build.sh'
    ]
    
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - NO ENCONTRADO")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n❌ Faltan archivos: {', '.join(missing_files)}")
        return False
    
    print("✅ Todos los archivos están presentes")
    return True

def check_cache_config():
    """Verifica la configuración del caché"""
    print("\n🔍 Verificando configuración de caché...")
    
    try:
        from app import app, cache
        print("✅ Flask app y caché inicializados correctamente")
        
        # Verificar configuración
        cache_type = app.config.get('CACHE_TYPE')
        cache_timeout = app.config.get('CACHE_DEFAULT_TIMEOUT')
        cache_prefix = app.config.get('CACHE_KEY_PREFIX')
        
        print(f"   - Tipo de caché: {cache_type}")
        print(f"   - Timeout: {cache_timeout} segundos")
        print(f"   - Prefijo: {cache_prefix}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en configuración de caché: {e}")
        return False

def check_imports():
    """Verifica que todos los imports funcionen"""
    print("\n🔍 Verificando imports...")
    
    try:
        from cache_manager import (
            get_current_date,
            get_historical_data_with_cache,
            get_current_data_only
        )
        print("✅ cache_manager imports correctos")
        
        from production_config import (
            get_production_cache_config,
            is_production
        )
        print("✅ production_config imports correctos")
        
        from api_historico import historico_bp
        print("✅ api_historico imports correctos")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en imports: {e}")
        return False

def check_endpoints():
    """Verifica que los endpoints de caché estén disponibles"""
    print("\n🔍 Verificando endpoints de caché...")
    
    try:
        from app import app
        
        # Verificar que el blueprint esté registrado
        if 'historico' in app.blueprints:
            print("✅ Blueprint historico registrado")
        else:
            print("❌ Blueprint historico NO registrado")
            return False
        
        # Verificar rutas específicas del caché
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        cache_endpoints = [
            '/api/dashboard/cache/status',
            '/api/dashboard/cache/clear'
        ]
        
        for endpoint in cache_endpoints:
            if endpoint in routes:
                print(f"✅ {endpoint}")
            else:
                print(f"❌ {endpoint} - NO ENCONTRADO")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando endpoints: {e}")
        return False

def check_environment():
    """Verifica variables de entorno"""
    print("\n🔍 Verificando variables de entorno...")
    
    # Variables opcionales pero importantes
    env_vars = [
        'MONGODB_URI',
        'FLASK_ENV',
        'RENDER'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var} = {value}")
        else:
            print(f"⚠️  {var} - NO DEFINIDA (opcional)")
    
    return True

def main():
    """Función principal de verificación"""
    print("=== VERIFICACIÓN DE DESPLIEGUE ===")
    print("MeteoSarria - Sistema de Caché Inteligente")
    print("")
    
    checks = [
        check_requirements,
        check_files,
        check_cache_config,
        check_imports,
        check_endpoints,
        check_environment
    ]
    
    all_passed = True
    
    for check in checks:
        if not check():
            all_passed = False
    
    print("\n" + "="*50)
    
    if all_passed:
        print("🎉 ¡TODAS LAS VERIFICACIONES PASARON!")
        print("✅ El sistema está listo para desplegar en Render")
        print("")
        print("📋 Pasos para el despliegue:")
        print("   1. git add .")
        print("   2. git commit -m 'Add intelligent cache system'")
        print("   3. git push origin main")
        print("   4. Render detectará los cambios y desplegará automáticamente")
        print("")
        print("🔧 Configuración en Render:")
        print("   - Build Command: pip install -r requirements.txt")
        print("   - Start Command: gunicorn --bind 0.0.0.0:$PORT app:app")
        print("   - Health Check: /api/dashboard/test")
        print("")
        print("📊 Beneficios esperados en producción:")
        print("   - 95-98% mejora en consultas repetidas")
        print("   - 90% reducción en consultas a MongoDB")
        print("   - Caché optimizado para Render")
        print("   - Datos actuales siempre frescos")
        
    else:
        print("❌ ALGUNAS VERIFICACIONES FALLARON")
        print("🔧 Corrige los errores antes de desplegar")
        sys.exit(1)

if __name__ == "__main__":
    main() 