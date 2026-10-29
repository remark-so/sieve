// Copies Arc's free components from its public registry into src/components/arc,
// following registryDependencies. Arc asks for its files to be copied as published,
// so this writes each file unchanged.
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

const items = process.argv.slice(2);
const seen = new Set();
const deps = new Set();

async function fetchItem(ref) {
  const url = ref.startsWith("http") ? ref : `https://uiarc.dev/r/${ref}.json`;
  if (seen.has(url)) return;
  seen.add(url);
  const item = await (await fetch(url)).json();
  for (const d of item.dependencies ?? []) deps.add(d);
  for (const file of item.files ?? []) {
    const target = file.target.replace(/^@components\//, "src/components/");
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, file.content);
    console.log("wrote", target);
  }
  for (const dep of item.registryDependencies ?? []) await fetchItem(dep);
}

for (const name of items) await fetchItem(name);
console.log("npm dependencies:", [...deps].join(" "));
