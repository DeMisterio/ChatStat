#!/usr/bin/env python3
import os
import sys
import argparse
import base64
from pathlib import Path

# Add project root to path so we can import backend.encryption
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.encryption import generate_key, encrypt_file

def main():
    parser = argparse.ArgumentParser(description="Подготовка зашифрованного файла для работы на арендованном GPU.")
    parser.add_argument("--input", required=True, help="Путь к исходному файлу (.json, .txt, .zip)")
    parser.add_argument("--output", required=True, help="Путь для сохранения зашифрованного файла (например, result.enc)")
    parser.add_argument("--key", help="Использовать существующий ключ (base64) вместо генерации нового")
    parser.add_argument("--save-key-to-file", action="store_true", help="ОПАСНО: Сохранить ключ в локальный файл (менее безопасно)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Ошибка: Файл {args.input} не найден.")
        return

    if args.key:
        try:
            key_b64 = args.key
            key_bytes = base64.b64decode(key_b64)
            if len(key_bytes) != 32:
                print("Ошибка: Ключ должен быть 256-битным (32 байта).")
                return
            print("🔑 Используется переданный ключ.")
        except Exception as e:
            print(f"Ошибка при чтении ключа: {e}")
            return
    else:
        # Generate key
        key_bytes = generate_key()
        key_b64 = base64.b64encode(key_bytes).decode('utf-8')
        print("🔑 Сгенерирован новый случайный ключ.")

    # Encrypt
    with open(input_path, "rb") as f:
        plaintext = f.read()

    try:
        ciphertext = encrypt_file(plaintext, key_bytes)
    except Exception as e:
        print(f"Ошибка при шифровании: {e}")
        return

    with open(args.output, "wb") as f:
        f.write(ciphertext)

    output_abs_path = Path(args.output).resolve()
    print(f"\n✅ Файл успешно зашифрован и сохранён по пути:\n{output_abs_path}")
    if not args.key:
        print("\nКЛЮЧ ДЛЯ РАСШИФРОВКИ:")
        print("-" * 50)
        print(key_b64)
        print("-" * 50)
        print("\n⚠️ ВНИМАНИЕ: Скопируйте этот ключ — он не сохраняется на диске по умолчанию!")
    
    print("Передайте ключ на удалённый инстанс через переменную окружения CHATSTAT_DECRYPT_KEY при запуске обработки.\n")

    if args.save_key_to_file:
        keys_dir = Path(__file__).resolve().parent / "generated_keys"
        keys_dir.mkdir(exist_ok=True)
        key_file = keys_dir / "key.txt"
        with open(key_file, "w") as f:
            f.write(key_b64)
        print(f"⚠️ Ключ сохранён в файл: {key_file}")
        print("Пожалуйста, убедитесь, что эта директория не попадает в публичные репозитории.\n")

if __name__ == "__main__":
    main()
