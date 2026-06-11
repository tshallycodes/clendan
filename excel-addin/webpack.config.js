const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const { execSync } = require("child_process");

const devCerts = (() => {
  try {
    return require("office-addin-dev-certs").getHttpsServerOptions();
  } catch {
    return {};
  }
})();

module.exports = async (env, options) => {
  const isDev = options.mode === "development";

  let https = false;
  if (isDev) {
    try {
      const certOptions = await require("office-addin-dev-certs").getHttpsServerOptions();
      https = certOptions;
    } catch {
      https = true;
    }
  }

  return {
    entry: {
      taskpane: "./src/taskpane/index.tsx",
      functions: "./src/functions/functions.ts",
    },
    output: {
      path: path.resolve(__dirname, "dist"),
      filename: "[name].js",
      clean: true,
    },
    resolve: {
      extensions: [".ts", ".tsx", ".js", ".jsx"],
    },
    module: {
      rules: [
        {
          test: /\.tsx?$/,
          use: "ts-loader",
          exclude: /node_modules/,
        },
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        filename: "taskpane.html",
        template: "./src/taskpane/taskpane.html",
        chunks: ["taskpane"],
      }),
      new HtmlWebpackPlugin({
        filename: "functions.html",
        template: "./src/functions/functions.html",
        chunks: ["functions"],
      }),
    ],
    devServer: {
      port: 3001,
      https,
      hot: true,
      headers: {
        "Access-Control-Allow-Origin": "*",
      },
    },
    devtool: isDev ? "source-map" : false,
  };
};
