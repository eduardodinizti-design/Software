// Bind the unmodified test server to our isolated loopback port.
// Business handlers and Python spawning are unchanged.
import net from 'node:net';
const original=net.Server.prototype.listen;
net.Server.prototype.listen=function(...args){
  if(args[0]===3000){args[0]=Number(process.env.AUDIT_LOCAL_PORT);args[1]='127.0.0.1';}
  return original.apply(this,args);
};
