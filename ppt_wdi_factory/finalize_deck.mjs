// Validate one private representative candidate without altering its source.
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [candidateArg, finalArg] = process.argv.slice(2);
const skillDir = process.env.PRESENTATIONS_SKILL_DIR;
const python = process.env.RUNTIME_PYTHON;
if (!candidateArg || !finalArg || !skillDir || !python) {
  throw new Error("Set candidate, output, PRESENTATIONS_SKILL_DIR and RUNTIME_PYTHON");
}
const candidatePath = path.resolve(candidateArg);
const finalPath = path.resolve(finalArg);
const workspaceDir = path.dirname(path.dirname(candidatePath));
const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);
await fs.mkdir(path.dirname(finalPath), { recursive: true });
const receiptDir = path.join(workspaceDir, "validation");
await fs.mkdir(receiptDir, { recursive: true });
const result = await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: python,
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000",
               "--validate-heading-fit", "--require-native-table-slide", "2",
               "--require-native-table-slide", "4"],
  explicitTotalSlideCount: 7,
  requiredNativeTableOwnerSlides: [2, 4],
  requiredNativeChartOwnerSlides: [3],
  materializeLiteralChartWorkbooks: true,
  fontPolicy: { basis: "design", families: ["Arial"] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(receiptDir,
    `${path.basename(path.dirname(finalPath))}-${path.basename(finalPath)}.json`),
});
console.log(JSON.stringify({ status: result.status, finalPath }));
