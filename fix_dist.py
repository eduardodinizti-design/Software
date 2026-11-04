path = 'dist/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('src="/assets/', 'src="assets/')
content = content.replace('href="/assets/', 'href="assets/')
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed dist/index.html successfully!')
