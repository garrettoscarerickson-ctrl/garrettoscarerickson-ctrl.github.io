const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1600,height:1260}});
await p.goto('file:///home/user/garrettoscarerickson-ctrl.github.io/d4-bracket/division4-bracket.html');await p.waitForTimeout(500);
await p.locator('#c').screenshot({path:'/home/user/garrettoscarerickson-ctrl.github.io/d4-bracket/division4-bracket.png'});await b.close()})();
