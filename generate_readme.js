const fs = require('fs');
const path = require('path');

const folders = ['Wallpapers_Global', 'Wallpapers_CN', 'Wallpapers_JP'];
let readmeContent = "# PGR Wallpaper Archive\n\n";

folders.forEach(folder => {
    if (fs.existsSync(folder)) {
        readmeContent += `## ${folder.replace('Wallpapers_', '')}\n\n`;
        const files = fs.readdirSync(folder).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f));
        files.forEach(file => {
            const relativePath = `${folder}/${encodeURIComponent(file)}`;
            readmeContent += `![${file}](${relativePath}) `;
        });
        readmeContent += "\n\n---\n\n";
    }
});

fs.writeFileSync('README.md', readmeContent);
console.log("✅ README.md has been updated!");
