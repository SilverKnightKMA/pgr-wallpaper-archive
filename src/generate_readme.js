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
const wallpapersBranch = config.wallpapersBranch || 'wallpapers';
const previewBranch = config.previewBranch || 'preview';

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Encode filename for use in URLs, preserving existing %XX sequences
function encodeFilename(filename) {
    return filename
        .replace(/[^A-Za-z0-9._~:@!$&'()*+,;=%\/-]/g, c => encodeURIComponent(c))
        .replace(/%(?![0-9A-Fa-f]{2})/g, '%25');
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
    const releaseTime = manifest.releaseTime || 'N/A';
    const pagesBaseUrl = `https://${repoSlug.split('/')[0]}.github.io/${repoSlug.split('/')[1]}/`;

    let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers from Punishing: Gray Raven.\n\n";
    readmeContent += `> Last Updated: ${new Date().toUTCString()}\n\n`;
    readmeContent += `🌐 [Browse & Filter Wallpapers on Web](${pagesBaseUrl})\n\n`;
    readmeContent += "## 📂 Server Galleries\n\n";
    readmeContent += `Each server's wallpapers are stored in the [\`${wallpapersBranch}\`](https://github.com/${repoSlug}/tree/${wallpapersBranch}) branch under per-server directories.\n\n`;
    readmeContent += "| Server | Directory | Gallery | Total | Success | Failed | Release Time |\n";
    readmeContent += "|--------|-----------|---------|-------|---------|--------|--------------|\n";

    config.servers.forEach(server => {
        const dirUrl = `https://github.com/${repoSlug}/tree/${wallpapersBranch}/${server.id}`;
        const serverData = manifest[server.id] || {};
        const total = serverData.total || 0;
        const success = serverData.success || 0;
        const failed = serverData.failed || 0;
        readmeContent += `| 🖼️ ${server.name} | \`${server.id}/\` | [View Gallery](${dirUrl}) | ${total} | ✅ ${success} | ❌ ${failed} | ${releaseTime} |\n`;
    });

    readmeContent += "\n---\n\n";

    // Wallpaper list per server with 18 most recent previews
    readmeContent += "## 🖼️ Wallpaper List\n\n";
    config.servers.forEach(server => {
        const serverData = manifest[server.id] || {};
        const wallpapers = serverData.wallpapers || [];
        const lastUpdated = serverData.lastUpdated || 'N/A';
        const total = serverData.total || 0;
        const previewReadmeUrl = `https://github.com/${repoSlug}/tree/${previewBranch}/${server.id}`;
        readmeContent += `### ${server.name}\n\n`;
        readmeContent += `> Last Updated: ${lastUpdated} | Total: ${total} wallpapers | Release Time: ${releaseTime}\n\n`;
        if (wallpapers.length > 0) {
            // Show preview images of the 18 most recent wallpapers
            const recent = wallpapers.slice(-18).reverse();
            readmeContent += "<p>\n";
            recent.forEach(w => {
                const filename = w.filename || 'unknown';
                const encodedFile = encodeFilename(filename);
                const safeFile = escapeHtml(filename);
                const thumbRawUrl = `https://raw.githubusercontent.com/${repoSlug}/${previewBranch}/${server.id}/thumbnails/${encodedFile}`;
                readmeContent += `<img src="${thumbRawUrl}" width="150" alt="${safeFile}" title="${safeFile}">\n`;
            });
            readmeContent += "</p>\n\n";
            if (wallpapers.length > 18) {
                readmeContent += `- ... and ${wallpapers.length - 18} more — [View all in Preview](${previewReadmeUrl})\n`;
            } else {
                readmeContent += `- [View all in Preview](${previewReadmeUrl})\n`;
            }
        } else {
            readmeContent += "_No wallpapers yet._\n";
        }
        readmeContent += "\n";
    });

    readmeContent += "---\n\n";

    readmeContent += "## 📦 Releases\n\n";
    readmeContent += `All wallpapers are also available as downloads in [Releases](https://github.com/${repoSlug}/releases).\n`;

    const outputPath = process.env.README_OUTPUT || path.join(__dirname, '../README.md');
    fs.writeFileSync(outputPath, readmeContent);
    console.log("✅ Main README.md updated!");
}

function generateBranchReadme(server) {
    const branchDir = process.env.BRANCH_DIR || path.join(__dirname, '..', 'branches', server.id);
    const imagesSubDir = path.join(branchDir, 'images');

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

    // Load manifest for releaseTime
    const manifest = loadManifest();
    const releaseTime = manifest.releaseTime || 'N/A';

    let readmeContent = `# ${server.name} — PGR Wallpaper Archive\n\n`;
    readmeContent += `> Total: ${allFiles.length} wallpapers | Last Updated: ${new Date().toUTCString()} | Release Time: ${releaseTime}\n\n`;
    readmeContent += `[⬅️ Back to Main](https://github.com/${repoSlug})\n\n`;

    // Link to GitHub Pages for full filtering
    const pagesUrl = `https://${repoSlug.split('/')[0]}.github.io/${repoSlug.split('/')[1]}/?server=${server.id}`;
    readmeContent += `🔍 [View & Filter on GitHub Pages](${pagesUrl})\n\n`;

    readmeContent += "## 🖼️ Gallery\n\n";

    if (allFiles.length === 0 && failedUrls.length === 0) {
        readmeContent += "_No wallpapers yet._\n";
    } else {
        // Build set of failed filenames for status lookup
        const failedFilenames = new Set();
        failedUrls.forEach(url => {
            try { failedFilenames.add(decodeURIComponent(url.split('/').pop())); } catch (e) { /* ignore */ }
        });

        // Single table with preview, path, link, status, release time
        readmeContent += "| Preview | Filename | Path | Download | Status | Release Time |\n";
        readmeContent += "|---------|----------|------|----------|--------|--------------|\n";
        allFiles.forEach(fileObj => {
            const file = fileObj.name;
            const encodedFile = encodeFilename(file);
            const safeFile = escapeHtml(file);
            // Preview uses raw URL from the preview branch
            const thumbRawUrl = `https://raw.githubusercontent.com/${repoSlug}/${previewBranch}/${server.id}/thumbnails/${encodedFile}`;
            // Download uses raw URL from the wallpapers branch
            const downloadUrl = `https://raw.githubusercontent.com/${repoSlug}/${wallpapersBranch}/${server.id}/images/${encodedFile}`;
            const imgPath = useSubDir ? `images/${encodedFile}` : encodedFile;
            const status = failedFilenames.has(file) ? '❌' : '✅';
            readmeContent += `| <img src="${thumbRawUrl}" width="100" alt="${safeFile}"> | \`${file}\` | \`${server.id}/${imgPath}\` | [Download](${downloadUrl}) | ${status} | ${releaseTime} |\n`;
        });
    }

    // Failed URLs section
    if (failedUrls.length > 0) {
        readmeContent += "\n## ⚠️ Broken Links\n\n";
        readmeContent += "The following URLs failed to download and will be retried on the next run:\n\n";
        readmeContent += "| # | URL | Status |\n";
        readmeContent += "|---|-----|--------|\n";
        failedUrls.forEach((url, i) => {
            readmeContent += `| ${i + 1} | \`${url}\` | ❌ Failed |\n`;
        });
        readmeContent += "\n";
    }

    const outputPath = process.env.BRANCH_README_OUTPUT || path.join(branchDir, 'README.md');
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, readmeContent);
    console.log(`✅ Branch README for ${server.name} updated at ${outputPath}!`);
}
