
Rules for Managing Fossils:

- Don't add verbose comments to `fossil.toml` configurations.

- Don't add verbose descriptions to fossil configurations.

- Always design analysis scripts to be generic w.r.t variants. Check if a
  suitable analysis script already exists before implementing a new one.

- A figure script should always be, within reason, composible from different
  subsets of variants. For instance, a bar graph with variants {A,B,C,D}
  should also render when records are selected from {A,B,C}



