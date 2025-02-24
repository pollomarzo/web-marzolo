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
        label: "forest",
        class: "forest",
        colors: {
            "--color-bg": "#2a4d3c",
            "--color-text": "#e8f3ed",
            "--color-accent": "#7cc69f",
            "--color-accent-text": "#1a332a",
            "--color-header": "#3d735a",
            "--color-header-text": "#e8f3ed"
        }
    }
];

export function applyTheme(theme: ThemeConfig) {
    for (const [prop, value] of Object.entries(theme.colors)) {
        document.documentElement.style.setProperty(prop, value);
        document.documentElement.classList.remove(
            ...themes.map((theme) => theme.class),
        );
        document.documentElement.classList.add(theme.class);

    }
}
