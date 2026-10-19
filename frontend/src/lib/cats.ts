import calico from "../assets/calico-cat.png";
import black from "../assets/black-cat.png";
import white from "../assets/white-cat.png";
import tabby from "../assets/maine-coon-cat.png";
import colorpoint from "../assets/rag-doll-cat.png";
export const cats: Record<
  string,
  { image: string; label: string; swatch: string }
> = {
  calico: { image: calico, label: "三花", swatch: "#c59167" },
  black: { image: black, label: "小黑", swatch: "#4b4b50" },
  white: { image: white, label: "雪白", swatch: "#e9e7e0" },
  tabby: { image: tabby, label: "橘猫", swatch: "#dfab69" },
  colorpoint: { image: colorpoint, label: "布偶", swatch: "#b8b2a8" },
};
