export interface ThemeConfig {
    label: string;
    class: string;
    colors: {
        "--color-bg": string;
        "--color-text": string;
        "--color-accent": string;
        "--color-accent-text": string;
        "--color-header": string;
        "--color-header-text": string;
    }
}

export const themes: ThemeConfig[] = [
    {
        label: "franz",
        class: "ff",
        colors: {
            "--color-bg": "#813405",
            "--color-text": "#fcfcfc",
            "--color-accent": "#d45113",
            "--color-accent-text": "black",
            "--color-header": "#f9a03f",
            "--color-header-text": "black",
        }
    },
    {
        label: "pp",
        class: "pp",
        colors: {
            "--color-bg": "#29335c",
            "--color-text": "white",
            "--color-accent": "#f3a712",
            "--color-accent-text": "black",
            "--color-header": "#1b9aaa",
            "--color-header-text": "black"
        }
    },
    {
        label: "bb",
        class: "bb",
        colors: {
            "--color-bg": "#fff0f5",
            "--color-text": "#4a4453",
            "--color-accent": "#b3e0ff",
            "--color-accent-text": "#00334d",
            "--color-header": "#ffb3d9",
            "--color-header-text": "#33001a"
        }
    },
    {
        label: "vv",
        class: "vv",
        colors: {
            "--color-bg": "#0a192f",
            "--color-text": "#f8f9fa",
            "--color-accent": "#ff6b6b",
            "--color-accent-text": "#0a192f",
            "--color-header": "#64ffda",
            "--color-header-text": "#020c1b"
        }
    },
    {
        label: "dd",
        class: "dd",
        colors: {
            "--color-bg": "#0066cc",
            "--color-text": "#ffffff",
            "--color-accent": "#ffd700",
            "--color-accent-text": "#003366",
            "--color-header": "#ff4444",
            "--color-header-text": "#ffffff"
        }
    },
    {
        label: "bibi",
        class: "bibi",
        colors: {
            "--color-bg": "#ffffff",
            "--color-text": "#000000",
            "--color-accent": "#666666",
            "--color-accent-text": "#ffffff",
            "--color-header": "#000000",
            "--color-header-text": "#ffffff"
        }
    },
    {
        label: "ee",
        class: "ee",
        colors: {
            "--color-bg": "#590d0d",
            "--color-text": "#ffe6e6",
            "--color-accent": "#ff6666",
            "--color-accent-text": "#330000",
            "--color-header": "#8c1a1a",
            "--color-header-text": "#fff0f0"
        }
    }
];

export const defaultTheme = themes[0];

function isString(data: unknown): data is string {
    return typeof data === 'string';
};

export function getTheme(theme: ThemeConfig | string) {
    if (isString(theme)) {
        let t = themes.find((t) => t.class === theme)
        if (!t) {
            console.error(`theme <${theme}> not found! using default...`)
            t = themes[0]
        }
        theme = t
    }
    return theme
}

export function applyTheme(theme: ThemeConfig | string, parent = document.documentElement) {
    // this function applies the theme to the root of the document, after including a transition
    parent.style.transition = "background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease, text-shadow 0.3s ease, filter 0.3s ease, opacity 0.3s ease";
    theme = getTheme(theme)
    for (const [prop, value] of Object.entries(theme.colors)) {
        parent.style.setProperty(prop, value);
        // let's also save the theme in localStorage
        localStorage.setItem("theme", theme.class)
    }
}
export function themeInCssVar(theme: ThemeConfig | string) {
    return Object.entries(getTheme(theme).colors).reduce((p, c) => p + `;${c[0]}:${c[1]}`, "")
}

const generateThemeCss = (theme: ThemeConfig): string => {
    const properties = Object.entries(theme.colors)
        .map(([variable, value]) => `  ${variable}: ${value};`)
        .join("\n");
    return `:root.${theme.class} {\n${properties}\n}`;
};

export const styleTagContentWithAllThemes = `
  <style is:global>
    ${themes
        .map((theme) => generateThemeCss(theme))
        .join("\n\n")}
  </style>
  `;
// this generates css made like this:
// :root.ff {
//   --color-bg: #813405;
//   --color-text: #fcfcfc;
//   ...
// }
// :root.pp {
//   --color-bg: #29335c;
//   --color-text: #ffffff;
//   ...
// }
// this is used to create all themes to enable switching between them