// 1. Import utilities from `astro:content`
import { defineCollection, z } from 'astro:content';

// 2. Import loader(s)
import { glob } from 'astro/loaders';

// 3. Define your collection(s)
const thoughts = defineCollection({
    loader: glob({ pattern: "**/*.json", base: "./src/bot_gen/thoughts" }),
    schema: z.object({
        author: z.string(),
        css_class: z.string(),
        datetime: z.string().datetime(),
        content: z.string(),
    })
});

const press = defineCollection({
    loader: glob({ pattern: "**/*.json", base: "./src/bot_gen/selected_press" }),
    schema: z.object({
        title: z.string(),
        url: z.string(),
        datetime: z.string().datetime(),
        // description is optional
        description: z.string().nullable(),
    })
});

// 4. Export a single `collections` object to register your collection(s)
export const collections = { thoughts, press };