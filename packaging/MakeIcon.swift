// Rasterize the app's authored three-bar vector mark for OS installer formats.
import AppKit
let image=NSImage(size:NSSize(width:1024,height:1024));image.lockFocus()
func color(_ r:CGFloat,_ g:CGFloat,_ b:CGFloat)->NSColor{NSColor(srgbRed:r/255,green:g/255,blue:b/255,alpha:1)}
color(62,54,169).setFill();NSBezierPath(roundedRect:NSRect(x:0,y:0,width:1024,height:1024),xRadius:220,yRadius:220).fill()
for (x,y,h,c) in [(290.0,314.0,380.0,color(238,231,255)),(457.0,220.0,584.0,color(225,244,178)),(624.0,280.0,464.0,color(255,199,219))]{c.setFill();NSBezierPath(roundedRect:NSRect(x:x,y:y,width:110,height:h),xRadius:55,yRadius:55).fill()}
image.unlockFocus();let cg=image.cgImage(forProposedRect:nil,context:nil,hints:nil)!;let bitmap=NSBitmapImageRep(cgImage:cg)
try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:CommandLine.arguments[1]))
