// Reads JSON {html, blocks:[css...]} on stdin, writes JSON {pruned:[css...]} to stdout.
// A rule is dropped only when every selector in it needs a class or id (outside :not/:is/:where/:has)
// that never appears in the page's markup or scripts. Everything else is kept untouched.
const csstree=require('css-tree');
let input='';process.stdin.on('data',d=>input+=d);process.stdin.on('end',()=>{
  const {html,blocks}=JSON.parse(input);
  const tokens=new Set(html.split(/[^A-Za-z0-9_-]+/).filter(Boolean));
  const prefixes=[...tokens].filter(t=>t.length>=3&&/-$/.test(t)&&/^[A-Za-z]/.test(t));
  const has=x=>tokens.has(x)||prefixes.some(p=>x.startsWith(p));
  const needed=sel=>{const req=[];sel.children.forEach(n=>{if(n.type==='ClassSelector'||n.type==='IdSelector')req.push(n.name);});return req.every(has);};
  function walk(list){list.forEach((node,item)=>{
    if(node.type==='Rule'){if(node.prelude.type!=='SelectorList')return;let any=false;node.prelude.children.forEach(s=>{if(needed(s))any=true;});if(!any)list.remove(item);}
    else if(node.type==='Atrule'&&node.block&&['media','supports','layer','container'].includes(node.name)){walk(node.block.children);if(node.block.children.isEmpty)list.remove(item);}
  });}
  const pruned=blocks.map(css=>{try{const ast=csstree.parse(css,{parseValue:false,parseAtrulePrelude:false,parseCustomProperty:false});walk(ast.children);return csstree.generate(ast);}catch(e){return css;}});
  process.stdout.write(JSON.stringify({pruned}));
});
