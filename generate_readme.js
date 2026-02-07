const fs = require('fs');
const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));

let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers.\n\n";

config.servers.forEach(server => {
    if (fs.existsSync(server.dir)) {
        readmeContent += `## 🖼️ ${server.name}\n\n`;
        const files = fs.readdirSync(server.dir).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f)).slice(0, 6); // Lấy 6 ảnh mới nhất
        
        readmeContent += "<table><tr>";
        files.forEach((file, index) => {
            const relativePath = `${server.dir}/${encodeURIComponent(file)}`;
            readmeContent += `<td><img src='${relativePath}' width='250'><br><sub>${file}</sub></td>`;
            if ((index + 1) % 3 === 0 && index !== files.length - 1) readmeContent += "</tr><tr>";
        });
        readmeContent += "</tr></table>\n\n---\n\n";
    }
});

fs.writeFileSync('README.md', readmeContent);
console.log("✅ README.md updated from config!");
