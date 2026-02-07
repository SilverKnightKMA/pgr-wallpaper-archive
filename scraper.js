const puppeteer = require('puppeteer');
const fs = require('fs');

async function getLinks(url, filename, selector) {
    console.log(`🚀 Task Started: Extracting links from ${url}`);
    const browser = await puppeteer.launch({ 
        headless: "new", 
        args: ['--no-sandbox', '--disable-setuid-sandbox'] 
    });
    const page = await browser.newPage();
    
    // 1. Set a large viewport to load more content initially
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    try {
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 90000 });

        // 2. Advanced Scroll Logic
        await page.evaluate(async () => {
            const delay = (ms) => new Promise(r => setTimeout(r, ms));
            
            // Auto-detect the correct scroll container
            const getContainer = () => {
                let node = document.querySelector('.wallpaper-list') || 
                           document.querySelector('.pns-picture') || 
                           document.querySelector('.pcWallpaper')?.parentElement ||
                           document.querySelector('#app');
                return (node && node.scrollHeight > node.clientHeight) ? node : document.documentElement;
            };

            const container = getContainer();
            let lastHeight = container.scrollHeight;
            let totalScrolled = 0;

            // Loop until no more content loads or we hit a safety limit
            for (let i = 0; i < 30; i++) {
                // Scroll both the window and the container to be safe
                window.scrollTo(0, document.body.scrollHeight);
                container.scrollBy(0, 1000); 
                
                await delay(2000); // Wait for images to load

                let newHeight = container.scrollHeight;
                if (newHeight === lastHeight) {
                    // Try one more time with a longer wait before giving up
                    await delay(2000);
                    if (container.scrollHeight === lastHeight) break;
                }
                lastHeight = newHeight;
                console.log(`Scrolled to height: ${newHeight}`);
            }
        });

        // 3. Extract Links
        const links = await page.evaluate((sel) => {
            const imgs = document.querySelectorAll(sel);
            return Array.from(imgs)
                .map(img => img.src)
                .filter(src => src && src.startsWith('http') && !src.includes('base64'))
                .map(url => encodeURI(decodeURI(url.replace(/\+/g, '%20'))));
        }, selector);

        const uniqueLinks = [...new Set(links)];
        fs.writeFileSync(filename, uniqueLinks.join('\n'));
        console.log(`✅ Success: Found ${uniqueLinks.length} links for ${filename}`);
    } catch (error) {
        console.error(`❌ Scraper Error: ${error.message}`);
    } finally {
        await browser.close();
    }
}

(async () => {
    // Global Site
    await getLinks(
        "https://pgr.kurogame.net/wallpapers", 
        "links_global.txt", 
        '.wallpaperItem1 img, .wallpaperItem2 img, .wallpaperItem3 img, .wallpaperItem4 img, .imgBox1 img, .imgBox2 img, .imgBox3 img, .imgBox4 img, .imgBox5 img, .imgBox6 img'
    );

    // CN Site
    await getLinks(
        "https://pns.kurogames.com/picture", 
        "links_cn.txt", 
        '.pcWallpaper img:not(.openDetail)'
    );

    // JP Site
    await getLinks(
        "https://pgr.kurogames.com/jp/picture", 
        "links_jp.txt", 
        '.pcWallpaper img:not(.openDetail)'
    );

    // KR Site
    await getLinks(
        "https://pgr.kurogames.com/kr/picture", 
        "links_kr.txt", 
        '.pcWallpaper img:not(.openDetail)'
    );

    // TW Site
    await getLinks(
        "https://pgr.kurogames.com/tw/picture", 
        "links_tw.txt", 
        '.pcWallpaper img:not(.openDetail)'
    );
})();
