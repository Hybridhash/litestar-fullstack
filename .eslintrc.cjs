module.exports = {
  root: true,
  env: { browser: true, es2020: true, node: true },
  extends: ["eslint:recommended", "prettier"],
  ignorePatterns: ["dist", ".eslintrc.cjs"],
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: "module",
  },
  rules: {
    "no-use-before-define": "off",
    "no-shadow": "off",
    "max-len": ["warn", { code: 120, ignoreComments: true, ignoreUrls: true }],
    "prettier/prettier": ["error", { endOfLine: "auto" }],
  },
}
