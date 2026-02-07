const fs = require('fs');
const path = require('path');
const configPath = path.join(__dirname, '../config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers.\n\n";
readmeContent += `> Last Updated: ${new Date().toUTCString()}\n\n`;

config.servers.forEach(server => {
    const absDir = path.join(__dirname, '../', server.dir);
    if (fs.existsSync(absDir)) {
        const allFiles = fs.readdirSync(absDir).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f));
        const sortedFiles = allFiles.map(name => ({
            name,
            time: fs.statSync(path.join(absDir, name)).mtime.getTime()
        }))
        .sort((a, b) => b.time - a.time)
        .slice(0, 9);

        readmeContent += `## 🖼️ ${server.name} (${allFiles.length} images)\n\n`;
        readmeContent += "<table><tr>";
        sortedFiles.forEach((fileObj, index) => {
            const file = fileObj.name;
            const relativePath = `${server.dir}/${encodeURIComponent(file)}`;
            readmeContent += `<td><img src='${relativePath}' width='250' title='${file}' alt='${file}'></td>`;
            if ((index + 1) % 3 === 0 && index !== sortedFiles.length - 1) readmeContent += "</tr><tr>";
        });
        readmeContent += "</tr></table>\n\n---\n\n";
    }
});

fs.writeFileSync(path.join(__dirname, '../README.md'), readmeContent);
console.log("✅ README.md updated!");
