const fs = require('fs');
const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));

console.log("📝 Generating README.md...");

let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers.\n\n";
readmeContent += `> Last Updated: ${new Date().toUTCString()}\n\n`;

config.servers.forEach(server => {
    if (fs.existsSync(server.dir)) {
        const allFiles = fs.readdirSync(server.dir).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f));
        // Sắp xếp theo thời gian file mới nhất lên đầu
        const sortedFiles = allFiles.map(name => ({
            name,
            time: fs.statSync(`${server.dir}/${name}`).mtime.getTime()
        }))
        .sort((a, b) => b.time - a.time)
        .slice(0, 9); // Lấy 9 ảnh mới nhất để làm gallery

        console.log(` - Processing ${server.name}: Found ${allFiles.length} total files.`);

        readmeContent += `## 🖼️ ${server.name} (${allFiles.length} images)\n\n`;
        readmeContent += "<table><tr>";
        
        sortedFiles.forEach((fileObj, index) => {
            const file = fileObj.name;
            const relativePath = `${server.dir}/${encodeURIComponent(file)}`;
            readmeContent += `<td><img src='${relativePath}' width='250'><br><sub>${file}</sub></td>`;
            if ((index + 1) % 3 === 0 && index !== sortedFiles.length - 1) readmeContent += "</tr><tr>";
        });
        
        readmeContent += "</tr></table>\n\n[View All](./" + server.dir + ")\n\n---\n\n";
    } else {
        console.log(` ! Skip ${server.name}: Directory not found.`);
    }
});

fs.writeFileSync('README.md', readmeContent);
console.log("✅ README.md has been updated successfully!");
