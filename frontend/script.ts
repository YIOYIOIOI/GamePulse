import fs from 'fs';
import path from 'path';

const files = fs.readdirSync(path.join(process.cwd(), 'src', 'views'))
  .filter(f => f.endsWith('.tsx'))
  .map(f => path.join('src', 'views', f));

files.forEach(file => {
  const filePath = path.join(process.cwd(), file);
  let content = fs.readFileSync(filePath, 'utf-8');

  content = content.replace(/dark:text-zinc-400 dark:text-zinc-500/g, 'dark:text-zinc-500');

  fs.writeFileSync(filePath, content, 'utf-8');
});

console.log('Cleanup Done!');
