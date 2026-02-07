const puppeteer = require('puppeteer');
const fs = require('fs');

async function getLinks(url, filename, selector) {
    console.log(`🚀 Task Started: Extracting links from ${url}`);
    const browser = await puppeteer.launch({ 
        headless: "new", 
        args: ['--no-sandbox', '--disable-setuid-sandbox'] 
    });
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    try {
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 90000 });

        await page.evaluate(async () => {
            const getContainer = () => {
                let node = document.querySelector('.wallpaper-list') || 
                           document.querySelector('.pns-picture') || 
                           document.querySelector('.pcWallpaper')?.parentElement ||
                           document.querySelector('#app');
                return (node && node.scrollHeight > node.clientHeight) ? node : document.documentElement;
            };
            const container = getContainer();
            let lastHeight = container.scrollHeight;
            for (let i = 0; i < 15; i++) {
                window.scrollBy(0, document.body.scrollHeight);
                container.scrollTo(0, container.scrollHeight);
                await new Promise(r => setTimeout(r, 2500));
                if (container.scrollHeight === lastHeight) break;
                lastHeight = container.scrollHeight;
            }
        });

        const links = await page.evaluate((sel) => {
            const imgs = document.querySelectorAll(sel);
            return Array.from(imgs)
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                .map(url => encodeURI(decodeURI(url.replace(/\+/g, '%20'))));
        }, selector);

        const uniqueLinks = [...new Set(links)];
        fs.writeFileSync(filename, uniqueLinks.join('\n'));
        console.log(`✅ Success: ${uniqueLinks.length} links saved to ${filename}`);
    } catch (error) {
        console.error(`❌ Scraper Error: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    await getLinks("https://pgr.kurogame.net/wallpapers", "links_global.txt", '.imgBox1 img, .imgBox2 img, .imgBox3 img, .imgBox4 img, .imgBox5 img, .imgBox6 img');
    await getLinks("https://pns.kurogames.com/picture", "links_cn.txt", '.pcWallpaper img:not(.openDetail)');
})();
