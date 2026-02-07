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

// Validate URL scheme (http/https only)
function isValidUrl(url) {
    try {
        const parsed = new URL(url);
        return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch (e) {
        return false;
    }
}

// Only run if executed directly (not when required as a module)
if (require.main === module) {
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
    const pagesBaseUrl = `https://${repoSlug.split('/')[0]}.github.io/${repoSlug.split('/')[1]}/`;

    let readmeContent = "# PGR Wallpaper Archive\n\nAutomated repository to archive high-quality wallpapers from Punishing: Gray Raven.\n\n";
    readmeContent += `🌐 [Browse & Filter Wallpapers on Web](${pagesBaseUrl})\n\n`;
    readmeContent += "## 📂 Server Galleries\n\n";
    readmeContent += `All wallpapers are stored in the [\`${wallpapersBranch}\`](https://github.com/${repoSlug}/tree/${wallpapersBranch}) branch.\n\n`;
    readmeContent += "| Server | Preview | Total | Success | Failed | Last Updated |\n";
    readmeContent += "|--------|---------|-------|---------|--------|---------------|\n";

    config.servers.forEach(server => {
        const previewUrl = `https://github.com/${repoSlug}/tree/${previewBranch}/${server.id}`;
        const serverData = manifest[server.id] || {};
        const total = serverData.total || 0;
        const success = serverData.success || 0;
        const failed = serverData.failed || 0;
        const lastUpdated = serverData.lastUpdated || 'N/A';
        readmeContent += `| 🖼️ ${server.name} | [View Preview](${previewUrl}) | ${total} | ✅ ${success} | ❌ ${failed} | ${lastUpdated} |\n`;
    });

    readmeContent += "\n---\n\n";

    // Wallpaper list per server with 15 most recent previews
    readmeContent += "## 🖼️ Wallpaper Preview\n\n";
    config.servers.forEach(server => {
        const serverData = manifest[server.id] || {};
        const wallpapers = serverData.wallpapers || [];
        const previewReadmeUrl = `https://github.com/${repoSlug}/tree/${previewBranch}/${server.id}`;
        readmeContent += `### ${server.name}\n\n`;
        if (wallpapers.length > 0) {
            // Show preview images of the 15 most recent wallpapers, linked to raw image
            const recent = wallpapers.slice(-15).reverse();
            readmeContent += "<p>\n";
            recent.forEach(w => {
                const filename = w.filename || 'unknown';
                const encodedFile = encodeFilename(filename);
                const safeFile = escapeHtml(filename);
                const thumbRawUrl = `https://raw.githubusercontent.com/${repoSlug}/${previewBranch}/${server.id}/thumbnails/${encodedFile}`;
                const rawUrl = `https://github.com/${repoSlug}/raw/${wallpapersBranch}/${encodedFile}`;
                readmeContent += `<a href="${rawUrl}"><img src="${thumbRawUrl}" width="150" alt="${safeFile}" title="${safeFile}"></a>\n`;
            });
            readmeContent += "</p>\n\n";
            if (wallpapers.length > 15) {
                readmeContent += `- ... and ${wallpapers.length - 15} more — [View all in Preview](${previewReadmeUrl})\n`;
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
    // Load manifest for wallpaper data
    const manifest = loadManifest();
    const serverData = manifest[server.id] || {};
    const wallpapers = serverData.wallpapers || [];
    const total = serverData.total || wallpapers.length;

    // Read failed URLs
    const failedFile = process.env.FAILED_FILE || path.join(__dirname, '..', 'Wallpapers', 'failed', `${server.id}.txt`);
    let failedUrls = [];
    if (fs.existsSync(failedFile)) {
        failedUrls = fs.readFileSync(failedFile, 'utf8').trim().split('\n').filter(Boolean);
    }

    // Build set of failed filenames for status lookup
    const failedFilenames = new Set();
    failedUrls.forEach(url => {
        try { failedFilenames.add(decodeURIComponent(url.split('/').pop())); } catch (e) { /* ignore */ }
    });

    const branchDir = process.env.BRANCH_DIR || path.join(__dirname, '..', 'branches', server.id);

    let readmeContent = `# ${server.name} — PGR Wallpaper Archive\n\n`;
    readmeContent += `> Total: ${total} wallpapers\n\n`;
    readmeContent += `[⬅️ Back to Main](https://github.com/${repoSlug})\n\n`;

    // Link to GitHub Pages for full filtering
    const pagesUrl = `https://${repoSlug.split('/')[0]}.github.io/${repoSlug.split('/')[1]}/?server=${server.id}`;
    readmeContent += `🔍 [View & Filter on GitHub Pages](${pagesUrl})\n\n`;

    readmeContent += "## 🖼️ Gallery\n\n";

    // Use manifest wallpapers sorted by releaseTime desc
    const sortedWallpapers = [...wallpapers].sort((a, b) => {
        const ta = a.releaseTime || '';
        const tb = b.releaseTime || '';
        return tb.localeCompare(ta);
    });

    if (sortedWallpapers.length === 0 && failedUrls.length === 0) {
        readmeContent += "_No wallpapers yet._\n";
    } else {
        // Responsive card-based layout using HTML (no horizontal scroll)
        sortedWallpapers.forEach(w => {
            const file = w.filename || 'unknown';
            const encodedFile = encodeFilename(file);
            const safeFile = escapeHtml(file);
            const thumbRawUrl = `https://raw.githubusercontent.com/${repoSlug}/${previewBranch}/${server.id}/thumbnails/${encodedFile}`;
            // Download raw from wallpapers branch (flat root) — LFS-safe URL
            const downloadUrl = `https://github.com/${repoSlug}/raw/${wallpapersBranch}/${encodedFile}`;
            const status = (w.status === 'failed' || failedFilenames.has(file)) ? '❌ Failed' : '✅ Success';
            const releaseTime = w.releaseTime || 'N/A';
            const size = w.size || 'N/A';
            const sourceUrl = w.url || '';
            const sourceLink = (sourceUrl && isValidUrl(sourceUrl)) ? `<a href="${escapeHtml(sourceUrl)}">🔗 Original</a>` : '';

            readmeContent += `<details>\n`;
            readmeContent += `<summary>\n`;
            readmeContent += `<img src="${thumbRawUrl}" width="200" alt="${safeFile}" title="${safeFile}"> <strong>${safeFile}</strong>\n`;
            readmeContent += `</summary>\n\n`;
            readmeContent += `- **Release Time:** ${releaseTime}\n`;
            readmeContent += `- **Size:** ${size}\n`;
            readmeContent += `- **Status:** ${status}\n`;
            readmeContent += `- **Download Raw:** [⬇ Download](${downloadUrl})\n`;
            if (sourceLink) {
                readmeContent += `- **Original:** ${sourceLink}\n`;
            }
            readmeContent += `\n</details>\n\n`;
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

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { encodeFilename, escapeHtml, isValidUrl };
}
