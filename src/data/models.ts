import type { Model } from "../types";
export const models: Record<
  Model,
  {
    name: string;
    case: string;
    edge: string;
    plate: string;
    alpha: string;
    mods: string;
    space: string;
    legend: string;
    description: string;
  }
> = {
  black: {
    name: "Mecha Mini · Black",
    case: "#292b2e",
    edge: "#111214",
    plate: "#121518",
    alpha: "#34373b",
    mods: "#34373b",
    space: "#34373b",
    legend: "#edf0f3",
    description: "Black aluminium · dark PBT",
  },
  llama: {
    name: "Mecha Mini · Frozen Llama",
    case: "#56b5ae",
    edge: "#318880",
    plate: "#294e54",
    alpha: "#7cd7ca",
    mods: "#6e9fbd",
    space: "#8764a8",
    legend: "#172d38",
    description: "Turquoise aluminium · mint, blue & purple",
  },
  creator: {
    name: "Mecha Mini · Creator",
    case: "#452957",
    edge: "#24172f",
    plate: "#382742",
    alpha: "#f3f1f4",
    mods: "#70488b",
    space: "#efebf2",
    legend: "#51465c",
    description: "Deep purple aluminium · pudding PBT",
  },
};
