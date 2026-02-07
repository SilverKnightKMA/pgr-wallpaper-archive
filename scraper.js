const puppeteer = require('puppeteer');
const fs = require('fs');
const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));

async function getLinks(server) {
    const timestamp = () => new Set().add(new Date().toLocaleTimeString()).values().next().value;
    console.log(`\n[${timestamp()}] 🚀 STARTING: ${server.name.toUpperCase()}`);
    
    const browser = await puppeteer.launch({ 
        headless: "new", 
        args: ['--no-sandbox', '--disable-setuid-sandbox'] 
    });
    
    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1920, height: 1080 });
        await page.setUserAgent(config.settings.userAgent);

        console.log(`[${timestamp()}] 🌐 Navigating to: ${server.url}`);
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 90000 });

        console.log(`[${timestamp()}] 🖱️  Scrolling to load content...`);
        await page.evaluate(async (maxScroll) => {
            const delay = (ms) => new Promise(r => setTimeout(r, ms));
            const container = document.documentElement;
            let lastHeight = container.scrollHeight;

            for (let i = 0; i < maxScroll; i++) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(2000);
                if (container.scrollHeight === lastHeight) break;
                lastHeight = container.scrollHeight;
            }
        }, config.settings.maxScrollAttempts);

        console.log(`[${timestamp()}] 🔍 Extracting links with selector: ${server.selector.substring(0, 30)}...`);
        const links = await page.evaluate((sel) => {
            return Array.from(document.querySelectorAll(sel))
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'));
        }, server.selector);

        const uniqueLinks = [...new Set(links)];
        fs.writeFileSync(server.txtPath, uniqueLinks.join('\n'));
        console.log(`[${timestamp()}] ✅ DONE: Saved ${uniqueLinks.length} unique links to ${server.txtPath}`);
        
    } catch (error) {
        console.error(`[${timestamp()}] ❌ ERROR [${server.id}]: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    console.log("=== PGR SCRAPER START ===");
    for (const server of config.servers) {
        await getLinks(server);
    }
    console.log("\n=== ALL SCRAPING TASKS FINISHED ===\n");
})();
