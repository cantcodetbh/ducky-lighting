export type Model = "black" | "llama" | "creator";
export type Layout = "ansi" | "iso";
export type Effect =
  "Static" | "Spectrum" | "Breathing" | "Wave" | "Reactive" | "Ripple";
export type Mode = "all" | "select" | "brush";
export interface Key {
  id: string;
  row: number;
  column: number;
  label: string;
  width: number;
  x: number;
  y: number;
  shape?: string;
  leds?: number[][];
}
export interface Scene {
  model: Model;
  layout: Layout;
  effect: Effect;
  color: string;
  brightness: number;
  speed: number;
  paints: Record<string, string>;
}
export interface Profile {
  id: string;
  name: string;
  scene: Scene;
}
export interface Trigger {
  x: number;
  y: number;
  at: number;
  id: string;
}
export interface DeviceStatus {
  mode: "demo" | "detected" | "available";
  connected: boolean;
  name: string;
  detail: string;
  device_id?: string;
  firmware?: string;
  capabilities: { rgb: boolean; effects: boolean };
  last_command?: unknown;
  can_quit?: boolean;
}
