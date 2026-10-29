import AppKit
final class AppDelegate:NSObject,NSApplicationDelegate {
 var started=false
 var pending:[URL]=[]
 var backend:Process?
 func applicationDidFinishLaunching(_ notification:Notification){
  let menu=NSMenu();let app=NSMenuItem();let sub=NSMenu();let open=NSMenuItem(title:"Open Ducky Lighting",action:#selector(openEditor),keyEquivalent:"o");open.target=self;sub.addItem(open);sub.addItem(.separator());let quit=NSMenuItem(title:"Quit Ducky Lighting",action:#selector(quitApp),keyEquivalent:"q");quit.target=self;sub.addItem(quit);app.submenu=sub;menu.addItem(app);NSApp.mainMenu=menu
  started=true
  if pending.isEmpty {launch(nil)} else {for url in pending {launch(url)};pending=[]}
 }
 func application(_ app:NSApplication,open urls:[URL]){for url in urls where url.scheme=="ducky-lighting" {if started {launch(url)}else{pending.append(url)}}}
 func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool {if started{launch(nil)};return false}
 @objc func openEditor(){launch(nil)}
 @objc func quitApp(){NSApp.terminate(nil)}
 func applicationWillTerminate(_ notification:Notification){if let process=backend,process.isRunning {process.terminate()}}
 func launch(_ url:URL?){
  let process=Process();process.executableURL=Bundle.main.resourceURL!.appendingPathComponent("companion/ducky-companion")
  process.arguments=url.map{[$0.absoluteString]} ?? []
  do{try process.run();if backend == nil || !(backend?.isRunning ?? false){backend=process}}
  catch{let alert=NSAlert();alert.messageText="Ducky Lighting could not start";alert.informativeText="The companion is missing or damaged. Reinstall Ducky Lighting from its verified release.";alert.runModal()}
 }
}
let app=NSApplication.shared
let delegate=AppDelegate();app.delegate=delegate
app.setActivationPolicy(.regular);app.run()
