const puppeteer = require('puppeteer');
const fs = require('fs');
const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));

async function getLinks(server) {
    console.log(`🚀 Task Started: ${server.name}`);
    const browser = await puppeteer.launch({ 
        headless: "new", 
        args: ['--no-sandbox', '--disable-setuid-sandbox'] 
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setUserAgent(config.settings.userAgent);
    
    try {
        await page.goto(server.url, { waitUntil: 'networkidle2', timeout: 90000 });

        await page.evaluate(async (maxScroll) => {
            const delay = (ms) => new Promise(r => setTimeout(r, ms));
            const container = document.documentElement; // Đơn giản hóa logic
            let lastHeight = container.scrollHeight;

            for (let i = 0; i < maxScroll; i++) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(2000);
                if (container.scrollHeight === lastHeight) break;
                lastHeight = container.scrollHeight;
            }
        }, config.settings.maxScrollAttempts);

        const links = await page.evaluate((sel) => {
            return Array.from(document.querySelectorAll(sel))
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'));
        }, server.selector);

        const uniqueLinks = [...new Set(links)];
        fs.writeFileSync(server.txtPath, uniqueLinks.join('\n'));
        console.log(`✅ Success: Found ${uniqueLinks.length} links for ${server.id}`);
    } catch (error) {
        console.error(`❌ Error [${server.id}]: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    for (const server of config.servers) {
        await getLinks(server);
    }
})();
