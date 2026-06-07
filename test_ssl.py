"""测试最小环境变量下 SSL 能否正常工作"""
import os
import subprocess

# 保留完整的环境变量，逐个尝试排除
test_env = {
    'DEEPSEEK_API_KEY': 'sk-7e1eee8aa79b4b7aa67e5e90eb6f6899',
    'PATH': os.environ.get('PATH', ''),
    'SYSTEMROOT': os.environ.get('SYSTEMROOT', 'C:\\Windows'),
    'TEMP': os.environ.get('TEMP', ''),
    'TMP': os.environ.get('TMP', ''),
    'USERPROFILE': os.environ.get('USERPROFILE', ''),
    'APPDATA': os.environ.get('APPDATA', ''),
    'LOCALAPPDATA': os.environ.get('LOCALAPPDATA', ''),
    'ALLUSERSPROFILE': os.environ.get('ALLUSERSPROFILE', ''),
    'COMMONPROGRAMFILES': os.environ.get('COMMONPROGRAMFILES', ''),
    'COMSPEC': os.environ.get('COMSPEC', ''),
    'DRIVERDATA': os.environ.get('DRIVERDATA', ''),
    'PATHEXT': os.environ.get('PATHEXT', ''),
    'PROCESSOR_ARCHITECTURE': os.environ.get('PROCESSOR_ARCHITECTURE', ''),
    'PROGRAMDATA': os.environ.get('PROGRAMDATA', ''),
    'PROGRAMFILES': os.environ.get('PROGRAMFILES', ''),
    'PSModulePath': os.environ.get('PSModulePath', ''),
    'PUBLIC': os.environ.get('PUBLIC', ''),
    'WINDIR': os.environ.get('WINDIR', ''),
}

# 逐个移除变量，找到哪个是关键
key_vars = ['APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ALLUSERSPROFILE']

for var in key_vars:
    env = dict(test_env)
    del env[var]
    try:
        result = subprocess.run(
            ['python', '-c', 'import urllib.request, ssl; r = urllib.request.urlopen("https://api.deepseek.com/v1/models", timeout=5, context=ssl.create_default_context()); print("OK:", r.status)'],
            capture_output=True, text=True, timeout=10, env=env
        )
        if 'OK' in result.stdout:
            print(f'Without {var}: OK')
        else:
            print(f'Without {var}: FAIL - {result.stderr[:80]}')
    except subprocess.TimeoutExpired:
        print(f'Without {var}: TIMEOUT')
    except Exception as e:
        print(f'Without {var}: ERROR - {e}')
