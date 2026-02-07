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
const imagesBranch = config.imagesBranch || 'images';

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

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

function loadManifest() {
    const manifestPath = process.env.MANIFEST_PATH || path.join(__dirname, '..', 'data', 'manifest.json');
    if (fs.existsSync(manifestPath)) {
        return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    }
    return {};
}

function generateMainReadme() {
    const manifest = loadManifest();

    let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers from Punishing: Gray Raven.\n\n";
    readmeContent += `> Last Updated: ${new Date().toUTCString()}\n\n`;
    readmeContent += "## 📂 Server Galleries\n\n";
    readmeContent += `Each server's wallpapers are stored in the [\`${imagesBranch}\`](https://github.com/${repoSlug}/tree/${imagesBranch}) branch under per-server directories.\n\n`;
    readmeContent += "| Server | Directory | Gallery | Total | Success | Failed |\n";
    readmeContent += "|--------|-----------|---------|-------|---------|--------|\n";

    config.servers.forEach(server => {
        const dirUrl = `https://github.com/${repoSlug}/tree/${imagesBranch}/${server.id}`;
        const serverData = manifest[server.id] || {};
        const total = serverData.total || 0;
        const success = serverData.success || 0;
        const failed = serverData.failed || 0;
        readmeContent += `| 🖼️ ${server.name} | \`${server.id}/\` | [View Gallery](${dirUrl}) | ${total} | ✅ ${success} | ❌ ${failed} |\n`;
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
    const imagesSubDir = path.join(branchDir, 'images');
    const thumbsDir = path.join(branchDir, 'thumbnails');

    // Read images from the images/ subdirectory
    const allFiles = [];
    const useSubDir = fs.existsSync(imagesSubDir);
    const imgDir = useSubDir ? imagesSubDir : branchDir;

    if (fs.existsSync(imgDir)) {
        fs.readdirSync(imgDir).forEach(f => {
            if (/\.(jpg|jpeg|png|webp)$/i.test(f)) {
                const stat = fs.statSync(path.join(imgDir, f));
                allFiles.push({ name: f, time: stat.mtime.getTime() });
            }
        });
    }
    allFiles.sort((a, b) => b.time - a.time);

    // Read failed URLs
    const failedFile = process.env.FAILED_FILE || path.join(__dirname, '..', 'Wallpapers', 'failed', `${server.id}.txt`);
    let failedUrls = [];
    if (fs.existsSync(failedFile)) {
        failedUrls = fs.readFileSync(failedFile, 'utf8').trim().split('\n').filter(Boolean);
    }

    // Group files by date for pagination
    const dateGroups = {};
    allFiles.forEach(fileObj => {
        const date = new Date(fileObj.time).toISOString().split('T')[0];
        if (!dateGroups[date]) dateGroups[date] = [];
        dateGroups[date].push(fileObj);
    });

    let readmeContent = `# ${server.name} — PGR Wallpaper Archive\n\n`;
    readmeContent += `> Total: ${allFiles.length} wallpapers | Last Updated: ${new Date().toUTCString()}\n\n`;
    readmeContent += `[⬅️ Back to Main](https://github.com/${repoSlug})\n\n`;
    readmeContent += "## 🖼️ Gallery\n\n";

    if (allFiles.length === 0) {
        readmeContent += "_No wallpapers yet._\n";
    } else {
        const sortedDates = Object.keys(dateGroups).sort((a, b) => b.localeCompare(a));
        sortedDates.forEach(date => {
            const files = dateGroups[date];
            readmeContent += `<details><summary>📅 ${date} (${files.length} images)</summary>\n\n`;
            readmeContent += "<table>\n";
            files.forEach((fileObj, index) => {
                if (index % 3 === 0) readmeContent += "<tr>\n";
                const file = fileObj.name;
                const encodedFile = encodeURIComponent(file);
                const safeFile = escapeHtml(file);
                const imgPath = useSubDir ? `images/${encodedFile}` : encodedFile;
                const hasThumb = fs.existsSync(path.join(thumbsDir, file));
                const thumbSrc = hasThumb ? `thumbnails/${encodedFile}` : imgPath;
                readmeContent += `<td align="center"><a href="${imgPath}"><img src="${thumbSrc}" width="250" title="${safeFile}" alt="${safeFile}"></a></td>\n`;
                if ((index + 1) % 3 === 0) readmeContent += "</tr>\n";
            });
            if (files.length % 3 !== 0) readmeContent += "</tr>\n";
            readmeContent += "</table>\n\n";
            readmeContent += "</details>\n\n";
        });
    }

    // Broken links section
    if (failedUrls.length > 0) {
        readmeContent += "## ⚠️ Broken Links\n\n";
        readmeContent += "The following URLs failed to download and will be retried on the next run:\n\n";
        readmeContent += "| # | URL |\n";
        readmeContent += "|---|-----|\n";
        failedUrls.forEach((url, i) => {
            readmeContent += `| ${i + 1} | \`${url}\` |\n`;
        });
        readmeContent += "\n";
    }

    const outputPath = process.env.BRANCH_README_OUTPUT || path.join(branchDir, 'README.md');
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, readmeContent);
    console.log(`✅ Branch README for ${server.name} updated at ${outputPath}!`);
}
