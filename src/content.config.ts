// 1. Import utilities from `astro:content`
import { defineCollection, z } from 'astro:content';

// 2. Import loader(s)
import { glob } from 'astro/loaders';

// "/src/pages/post/**/*.(md|mdx)"
// "/src/thoughts/**/*.(json)"

// 3. Define your collection(s)
// const blog = defineCollection({
//     loader: glob({ pattern: "**/*.(md|mdx)", base: "/src/pages/post" })
// });
const thoughts = defineCollection({
    loader: glob({ pattern: "**/*.json", base: "./src/bot_gen/thoughts" }),
    schema: z.object({
        author: z.string(),
        css_class: z.string(),
        datetime: z.string().datetime(),
        content: z.string(),
    })
});

// 4. Export a single `collections` object to register your collection(s)
export const collections = { thoughts };