"""
Funksiyalar:
1. Fayl Tizimi Analizatori
2. HTTP Client va API Tester
3. Tasvir Qayta Ishlash
4. Web Scraper
"""

import os
import sys
import time
import json
import csv
import sqlite3
import hashlib
import base64
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from urllib.parse import urljoin, urlparse

# Optional imports (xato bo'lsa o'tkazib yuborish)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("⚠️  'requests' kutubxonasi topilmadi. HTTP funksiyalar ishlamaydi.")

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  'Pillow' kutubxonasi topilmadi. Tasvir funksiyalar ishlamaydi.")


# ============================================================================
# 1. FAYL TIZIMI ANALIZATORI
# ============================================================================

class FileSystemAnalyzer:
    """Fayl tizimini tahlil qiluvchi klass"""
    
    def __init__(self, root_path):
        self.root_path = Path(root_path)
        self.stats = defaultdict(int)
        self.duplicates = defaultdict(list)
        self.file_types = defaultdict(list)
        
    def calculate_file_hash(self, filepath, block_size=65536):
        """Fayl hash qiymatini hisoblash"""
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(block_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, OSError):
            return None
    
    def format_size(self, size_bytes):
        """Baytlarni o'qish oson formatga o'tkazish"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def analyze_directory(self, find_duplicates=False):
        """Katalogni to'liq tahlil qilish"""
        print(f"\n🔍 Tahlil: {self.root_path}")
        print("=" * 60)
        
        total_size = 0
        file_hashes = {}
        
        for item in self.root_path.rglob('*'):
            if item.is_file():
                try:
                    size = item.stat().st_size
                    total_size += size
                    self.stats['total_files'] += 1
                    
                    extension = item.suffix.lower() or 'no_extension'
                    self.file_types[extension].append({
                        'path': str(item),
                        'size': size
                    })
                    
                    if find_duplicates:
                        file_hash = self.calculate_file_hash(item)
                        if file_hash:
                            if file_hash in file_hashes:
                                self.duplicates[file_hash].append(str(item))
                            else:
                                file_hashes[file_hash] = str(item)
                                self.duplicates[file_hash].append(str(item))
                    
                except (PermissionError, OSError):
                    self.stats['errors'] += 1
                    
            elif item.is_dir():
                self.stats['total_dirs'] += 1
        
        self.stats['total_size'] = total_size
        self.print_report()
        return self.stats
    
    def print_report(self):
        """Hisobotni chop etish"""
        print(f"\n📊 STATISTIKA")
        print("=" * 60)
        print(f"Fayllar: {self.stats['total_files']}")
        print(f"Kataloglar: {self.stats['total_dirs']}")
        print(f"Hajm: {self.format_size(self.stats['total_size'])}")
        
        print(f"\n📁 FAYL TURLARI")
        print("=" * 60)
        sorted_types = sorted(
            self.file_types.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        
        for ext, files in sorted_types:
            total = sum(f['size'] for f in files)
            print(f"{ext:20} | {len(files):5} ta | {self.format_size(total)}")


# ============================================================================
# 2. HTTP CLIENT VA API TESTER
# ============================================================================

class HTTPClient:
    """HTTP so'rovlar uchun client"""
    
    def __init__(self, timeout=30):
        if not HAS_REQUESTS:
            raise ImportError("requests kutubxonasi kerak!")
        
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Python-Swiss-Army-Knife/1.0'
        })
        self.history = []
    
    def request(self, method, url, **kwargs):
        """Universal HTTP so'rov"""
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        start_time = time.time()
        
        try:
            response = self.session.request(method, url, **kwargs)
            elapsed = time.time() - start_time
            
            self.history.append({
                'method': method,
                'url': url,
                'status': response.status_code,
                'elapsed': round(elapsed, 3)
            })
            
            return response
        except Exception as e:
            print(f"❌ Xato: {e}")
            raise
    
    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)
    
    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)
    
    def print_response(self, response):
        """Javobni chiroyli chop etish"""
        print("\n" + "=" * 70)
        print(f"📡 {response.request.method} {response.url}")
        print("=" * 70)
        
        status_emoji = "✅" if 200 <= response.status_code < 300 else "❌"
        print(f"{status_emoji} Status: {response.status_code}")
        print(f"⏱️  Vaqt: {response.elapsed.total_seconds():.3f}s")
        print(f"📦 Hajm: {len(response.content)} bytes")
        
        # JSON javob
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            try:
                data = response.json()
                print(f"\n📄 JSON:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
            except:
                print(response.text[:500])
        else:
            print(f"\n📄 Text:")
            print(response.text[:500])
        
        print("=" * 70)


class APITester:
    """API test qilish"""
    
    def __init__(self, base_url):
        if not HAS_REQUESTS:
            raise ImportError("requests kutubxonasi kerak!")
        
        self.base_url = base_url
        self.client = HTTPClient()
        self.results = []
    
    def test_endpoint(self, method, endpoint, expected_status=200, **kwargs):
        """Endpoint test qilish"""
        print(f"\n🧪 Test: {method} {endpoint}")
        
        try:
            url = urljoin(self.base_url, endpoint)
            response = self.client.request(method, url, **kwargs)
            
            passed = response.status_code == expected_status
            
            if passed:
                print(f"  ✅ PASS - Status: {response.status_code}")
            else:
                print(f"  ❌ FAIL - Expected: {expected_status}, Got: {response.status_code}")
            
            self.results.append({
                'endpoint': endpoint,
                'method': method,
                'passed': passed
            })
            
            return passed
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            return False
    
    def run_tests(self, tests):
        """Ko'p testlarni bajarish"""
        print(f"\n🧪 Test Suite: {len(tests)} ta")
        print("=" * 60)
        
        for test in tests:
            self.test_endpoint(**test)
        
        passed = sum(1 for r in self.results if r['passed'])
        print(f"\n📊 Natija: {passed}/{len(self.results)} o'tdi")


# ============================================================================
# 3. TASVIR QAYTA ISHLASH
# ============================================================================

class ImageProcessor:
    """Tasvir qayta ishlash"""
    
    def __init__(self, output_dir='processed'):
        if not HAS_PIL:
            raise ImportError("Pillow kutubxonasi kerak!")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def load_image(self, path):
        """Tasvirni yuklash"""
        img = Image.open(path)
        print(f"✓ Yuklandi: {path}")
        print(f"  O'lcham: {img.size[0]}x{img.size[1]}")
        print(f"  Format: {img.format}")
        return img
    
    def resize(self, img, width, height):
        """O'lchamni o'zgartirish"""
        resized = img.resize((width, height), Image.Resampling.LANCZOS)
        print(f"✓ Resize: {width}x{height}")
        return resized
    
    def apply_filter(self, img, filter_name):
        """Filter qo'llash"""
        filters = {
            'blur': ImageFilter.BLUR,
            'sharpen': ImageFilter.SHARPEN,
            'contour': ImageFilter.CONTOUR,
            'emboss': ImageFilter.EMBOSS
        }
        
        if filter_name in filters:
            filtered = img.filter(filters[filter_name])
            print(f"✓ Filter: {filter_name}")
            return filtered
        return img
    
    def grayscale(self, img):
        """Oq-qora"""
        gray = img.convert('L')
        print("✓ Grayscale")
        return gray
    
    def save(self, img, filename):
        """Saqlash"""
        output = self.output_dir / filename
        img.save(output)
        print(f"✅ Saqlandi: {output}")
        return output


# ============================================================================
# 4. WEB SCRAPER
# ============================================================================

class WebScraper:
    """Veb ma'lumotlar yig'ish"""
    
    def __init__(self):
        if not HAS_REQUESTS:
            raise ImportError("requests kutubxonasi kerak!")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 Python-Tool/1.0'
        })
    
    def fetch_json_api(self, url, params=None):
        """JSON API dan ma'lumot olish"""
        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Xato: {e}")
            return None
    
    def save_json(self, data, filename):
        """JSON ga saqlash"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Saqlandi: {filename}")
    
    def save_csv(self, data, filename):
        """CSV ga saqlash"""
        if not data:
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ Saqlandi: {filename}")


# ============================================================================
# DEMO FUNKSIYALAR
# ============================================================================

def demo_file_analyzer():
    """Fayl analizator demo"""
    print("\n" + "FAYL ANALIZATOR DEMO".center(70, "="))
    
    path = input("Katalog yo'li (enter = joriy katalog): ").strip() or "."
    
    if not os.path.exists(path):
        print(f"❌ '{path}' topilmadi!")
        return
    
    analyzer = FileSystemAnalyzer(path)
    analyzer.analyze_directory(find_duplicates=False)


def demo_http_client():
    """HTTP client demo"""
    print("\n" + "HTTP CLIENT DEMO".center(70, "="))
    
    if not HAS_REQUESTS:
        print("❌ 'requests' kutubxonasi kerak!")
        print("   pip install requests --break-system-packages")
        return
    
    print("\nTest URL: https://jsonplaceholder.typicode.com/posts/1")
    
    try:
        client = HTTPClient()
        response = client.get('https://jsonplaceholder.typicode.com/posts/1')
        client.print_response(response)
    except Exception as e:
        print(f"❌ Xato: {e}")


def demo_image_processor():
    """Tasvir qayta ishlash demo"""
    print("\n" + "IMAGE PROCESSOR DEMO".center(70, "="))
    
    if not HAS_PIL:
        print("❌ 'Pillow' kutubxonasi kerak!")
        print("   pip install Pillow --break-system-packages")
        return
    
    image_path = input("Tasvir fayl yo'li: ").strip()
    
    if not os.path.exists(image_path):
        print(f"❌ '{image_path}' topilmadi!")
        return
    
    processor = ImageProcessor()
    img = processor.load_image(image_path)
    
    print("\nQaysi amal bajarilsin?")
    print("1. Resize (800x600)")
    print("2. Grayscale")
    print("3. Blur filter")
    print("4. Sharpen filter")
    
    choice = input("\nTanlang (1-4): ").strip()
    
    if choice == '1':
        img = processor.resize(img, 800, 600)
    elif choice == '2':
        img = processor.grayscale(img)
    elif choice == '3':
        img = processor.apply_filter(img, 'blur')
    elif choice == '4':
        img = processor.apply_filter(img, 'sharpen')
    
    output_name = f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    processor.save(img, output_name)


def demo_web_scraper():
    """Web scraper demo"""
    print("\n" + "WEB SCRAPER DEMO".center(70, "="))
    
    if not HAS_REQUESTS:
        print("❌ 'requests' kutubxonasi kerak!")
        return
    
    print("\nPublic API test: JSONPlaceholder")
    
    scraper = WebScraper()
    
    print("\n1. Posts olish...")
    posts = scraper.fetch_json_api('https://jsonplaceholder.typicode.com/posts')
    
    if posts:
        print(f"✅ {len(posts)} ta post olindi")
        print(f"\nBirinchi post:")
        print(json.dumps(posts[0], indent=2))
        
        save = input("\nJSON ga saqlashmi? (y/n): ").strip().lower()
        if save == 'y':
            scraper.save_json(posts[:10], 'posts.json')


# ============================================================================
# ASOSIY MENYU
# ============================================================================

def show_menu():
    """Asosiy menyu"""
    print("\n" + "=" * 70)
    print("🛠️  PYTHON SWISS ARMY KNIFE".center(70))
    print("=" * 70)
    print("\n1. 📁 Fayl Tizimi Analizatori")
    print("2. 🌐 HTTP Client va API Tester")
    print("3. 🖼️  Tasvir Qayta Ishlash")
    print("4. 🕷️  Web Scraper")
    print("5. ℹ️  Ma'lumot")
    print("0. ❌ Chiqish")
    print("\n" + "=" * 70)


def show_info():
    """Tool haqida ma'lumot"""
    print("\n" + "=" * 70)
    print("Python Swiss Army Knife - Barcha funksiyalar bitta joyda")
    print("=" * 70)
    print("\nMuallif: GitHub User")
    print("Versiya: 1.0.0")
    print("Til: Python 3.6+")
    
    print("\nKerakli kutubxonalar:")
    print(f"  • requests: {'✅ O\'rnatilgan' if HAS_REQUESTS else '❌ Yo\'q'}")
    print(f"  • Pillow: {'✅ O\'rnatilgan' if HAS_PIL else '❌ Yo\'q'}")
    
    if not HAS_REQUESTS or not HAS_PIL:
        print("\nO'rnatish:")
        if not HAS_REQUESTS:
            print("  pip install requests --break-system-packages")
        if not HAS_PIL:
            print("  pip install Pillow --break-system-packages")
    
    print("\nGitHub: github.com/yourusername/python-swiss-army-knife")
    print("=" * 70)


def main():
    """Asosiy dastur"""
    parser = argparse.ArgumentParser(
        description='Python Swiss Army Knife - Ko\'p maqsadli tool',
        epilog='Menyu uchun argumentsiz ishga tushiring'
    )
    
    parser.add_argument('--analyze', metavar='PATH', help='Katalogni tahlil qilish')
    parser.add_argument('--http-get', metavar='URL', help='HTTP GET so\'rov')
    parser.add_argument('--test-api', metavar='URL', help='API test qilish')
    parser.add_argument('--process-image', metavar='FILE', help='Tasvirni qayta ishlash')
    parser.add_argument('--scrape', metavar='URL', help='URL dan ma\'lumot olish')
    
    args = parser.parse_args()
    
    # CLI mode
    if args.analyze:
        analyzer = FileSystemAnalyzer(args.analyze)
        analyzer.analyze_directory()
        return
    
    if args.http_get:
        if HAS_REQUESTS:
            client = HTTPClient()
            response = client.get(args.http_get)
            client.print_response(response)
        else:
            print("❌ 'requests' kutubxonasi kerak!")
        return
    
    if args.test_api:
        if HAS_REQUESTS:
            tester = APITester(args.test_api)
            tests = [
                {'method': 'GET', 'endpoint': '/posts', 'expected_status': 200},
                {'method': 'GET', 'endpoint': '/posts/1', 'expected_status': 200}
            ]
            tester.run_tests(tests)
        else:
            print("❌ 'requests' kutubxonasi kerak!")
        return
    
    # Interactive mode
    while True:
        show_menu()
        
        choice = input("\nTanlang (0-5): ").strip()
        
        if choice == '1':
            demo_file_analyzer()
        elif choice == '2':
            demo_http_client()
        elif choice == '3':
            demo_image_processor()
        elif choice == '4':
            demo_web_scraper()
        elif choice == '5':
            show_info()
        elif choice == '0':
            print("\n👋 Xayr!")
            break
        else:
            print("\n❌ Noto'g'ri tanlov!")
        
        input("\nDavom etish uchun Enter...")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Dastur to'xtatildi!")
    except Exception as e:
        print(f"\n❌ Xato: {e}")
