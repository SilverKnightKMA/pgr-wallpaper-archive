const fs = require('fs');
const path = require('path');
const configPath = path.join(__dirname, '..', 'config.json');

if (!fs.existsSync(configPath)) {
    console.error(`❌ Config not found: ${configPath}`);
    process.exit(1);
}

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const mode = process.argv[2] || 'main'; // 'main' or 'branch'
const serverId = process.argv[3];       // server id for branch mode
const repoSlug = process.env.GITHUB_REPOSITORY || 'SilverKnightKMA/pgr-wallpaper-archive';

if (mode === 'main') {
    generateMainReadme();
} else if (mode === 'branch') {
    if (!serverId) {
        console.error('❌ Server ID required for branch mode');
        process.exit(1);
    }
    const server = config.servers.find(s => s.id === serverId);
    if (!server) {
        console.error(`❌ Server not found: ${serverId}`);
        process.exit(1);
    }
    generateBranchReadme(server);
}

function generateMainReadme() {
    let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers from Punishing: Gray Raven.\n\n";
    readmeContent += `> Last Updated: ${new Date().toUTCString()}\n\n`;
    readmeContent += "## 📂 Server Galleries\n\n";
    readmeContent += "Each server's wallpapers are stored in a dedicated branch.\n\n";
    readmeContent += "| Server | Branch | Gallery |\n";
    readmeContent += "|--------|--------|----------|\n";

    config.servers.forEach(server => {
        const branchUrl = `https://github.com/${repoSlug}/tree/${server.branch}`;
        readmeContent += `| 🖼️ ${server.name} | \`${server.branch}\` | [View Gallery](${branchUrl}) |\n`;
    });

    readmeContent += "\n---\n\n";
    readmeContent += "## 📦 Releases\n\n";
    readmeContent += `All wallpapers are also available as downloads in [Releases](https://github.com/${repoSlug}/releases).\n`;

    const outputPath = process.env.README_OUTPUT || path.join(__dirname, '../README.md');
    fs.writeFileSync(outputPath, readmeContent);
    console.log("✅ Main README.md updated!");
}

function generateBranchReadme(server) {
    const branchDir = process.env.BRANCH_DIR || path.join(__dirname, '..', 'branches', server.id);
    const thumbsDir = path.join(branchDir, 'thumbnails');
    const imagesDir = branchDir;

    const allFiles = [];
    if (fs.existsSync(imagesDir)) {
        fs.readdirSync(imagesDir).forEach(f => {
            if (/\.(jpg|jpeg|png|webp)$/i.test(f)) {
                const stat = fs.statSync(path.join(imagesDir, f));
                allFiles.push({ name: f, time: stat.mtime.getTime() });
            }
        });
    }
    allFiles.sort((a, b) => b.time - a.time);

    let readmeContent = `# ${server.name} — PGR Wallpaper Archive\n\n`;
    readmeContent += `> Total: ${allFiles.length} wallpapers | Last Updated: ${new Date().toUTCString()}\n\n`;
    readmeContent += `[⬅️ Back to Main](https://github.com/${repoSlug})\n\n`;
    readmeContent += "## 🖼️ Gallery\n\n";

    if (allFiles.length === 0) {
        readmeContent += "_No wallpapers yet._\n";
    } else {
        readmeContent += "<table>\n";
        allFiles.forEach((fileObj, index) => {
            if (index % 3 === 0) readmeContent += "<tr>\n";
            const file = fileObj.name;
            const encodedFile = encodeURIComponent(file);
            const hasThumb = fs.existsSync(path.join(thumbsDir, file));
            const thumbSrc = hasThumb ? `thumbnails/${encodedFile}` : encodedFile;
            readmeContent += `<td align="center"><a href="${encodedFile}"><img src="${thumbSrc}" width="250" title="${file}" alt="${file}"></a></td>\n`;
            if ((index + 1) % 3 === 0) readmeContent += "</tr>\n";
        });
        // Close last row if not evenly divisible by 3
        if (allFiles.length % 3 !== 0) readmeContent += "</tr>\n";
        readmeContent += "</table>\n";
    }

    const outputPath = process.env.BRANCH_README_OUTPUT || path.join(branchDir, 'README.md');
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, readmeContent);
    console.log(`✅ Branch README for ${server.name} updated at ${outputPath}!`);
}
