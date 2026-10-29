// Puts the built single-file page where sieve.py looks for it.
import { copyFile } from "node:fs/promises";
await copyFile("dist/index.html", "../skills/sieve/dashboard.html");
console.log("wrote skills/sieve/dashboard.html");
