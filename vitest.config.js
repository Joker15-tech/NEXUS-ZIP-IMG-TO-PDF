import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        // ─── Environnement ───────────────────────────────────────────
        globals: true,
        environment: 'jsdom',
        environmentOptions: {
            jsdom: {
                // URL par défaut — évite les "Failed to parse URL" avec Blob
                url: 'http://localhost/',
                // Nécessaire pour `localStorage` dans jsdom
                pretendToBeVisual: true,
            },
        },

        // ─── Découverte des tests ────────────────────────────────────
        include: [
            'tests/**/*.{test,spec}.{js,mjs}',
        ],
        exclude: [
            'node_modules/**',
            'coverage/**',
            'htmlcov/**',
            'dist/**',
            'python/**',
            'shared/**/*.py',
            'tests/**/*.py',
            'tests/setup.js',      // ← setup, pas un test
            'tests/conftest.py',
        ],

        // ─── Setup global ────────────────────────────────────────────
        setupFiles: ['./tests/setup.js'],

        // ─── Timeouts ────────────────────────────────────────────────
        testTimeout: 15000,   // ZIP+PDF de 50 images peut prendre >5s
        hookTimeout: 15000,
        teardownTimeout: 10000,

        // ─── Comportement des mocks ──────────────────────────────────
        // Le setup.js gère clearAllMocks() manuellement dans beforeEach.
        // On laisse ces options à false pour ne pas interférer.
        clearMocks: false,
        restoreMocks: false,
        mockReset: false,

        // ─── Isolation ───────────────────────────────────────────────
        isolate: true,             // chaque fichier dans son propre contexte
        pool: 'threads',           // threads = plus rapide que processes

        // ─── Reporters ───────────────────────────────────────────────
        reporters: ['default'],
        outputFile: {
            junit: './coverage/junit.xml',
        },

        // ─── Coverage ────────────────────────────────────────────────
        coverage: {
            provider: 'v8',
            enabled: false,        // ← opt-in via `npm run test:coverage`
            reportsDirectory: './coverage',

            reporter: ['text', 'json', 'html', 'lcov'],

            include: [
                'shared/**/*.js',
                'web/**/*.js',
            ],
            exclude: [
                'node_modules/**',
                'tests/**',
                '**/*.test.js',
                '**/*.spec.js',
                '**/*.config.js',
                '**/*.min.js',
            ],

            // `all: true` est déprécié dans Vitest 1.x — l'effet est
            // déjà obtenu par la présence de `include`.
            all: false,

            // Seuils globaux (agrégés sur tous les fichiers).
            // perFile: false → le seuil s'applique à la moyenne, pas
            //                  à chaque fichier individuellement.
            perFile: false,
            lines: 80,
            functions: 80,
            branches: 70,       // branches plus permissif (beaucoup d'if/else)
            statements: 80,

            // Décommenter pour exiger des seuils par fichier :
            // perFile: true,
        },

        // ─── Comportement des logs ───────────────────────────────────
        silent: false,
        onConsoleLog(log, type) {
            // Filtre les console.log bruyants de jsdom / ResizeObserver
            if (type === 'stderr' && log.includes('ResizeObserver')) {
                return false;
            }
            if (type === 'stderr' && log.includes('Not implemented: HTMLCanvasElement')) {
                return false;
            }
            return true;
        },
    },

    // ─── Résolution des modules ──────────────────────────────────────
    // Force Vitest à résoudre jszip/jspdf même quand ils sont mockés.
    // Sans ça, un `vi.mock('jszip')` peut émettre un warning si le
    // package n'est pas trouvé dans node_modules.
    resolve: {
        alias: {
            // Alias vers le vrai package s'il existe, sinon Vitest
            // utilise le mock factory dans les tests.
        },
    },

    // ─── Dépendances à inliner ───────────────────────────────────────
    // Nécessaire si des packages ESM/CJS posent problème.
    ssr: {
        noExternal: [
            'jszip',
            'jspdf',
        ],
    },
});
