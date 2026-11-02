"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseBatchBuffer = parseBatchBuffer;
const errorHandeling_1 = require("../utils/errorHandeling");
const errrorcode_1 = require("../config/errrorcode");
function parseBatchBuffer(buffer, originalName = "", mimetype = "") {
    const text = buffer.toString("utf8").replace(/^\uFEFF/, "").trim();
    if (!text) {
        throw (0, errorHandeling_1.handleError)("Uploaded file is empty.", 400, errrorcode_1.errorCode.invalid);
    }
    const format = detectFormat(text, originalName, mimetype);
    let events;
    switch (format) {
        case "json":
            events = parseJson(text);
            break;
        case "jsonl":
            events = parseJsonLines(text);
            break;
        case "csv":
            events = parseCsv(text);
            break;
    }
    if (!Array.isArray(events) || events.length === 0) {
        throw (0, errorHandeling_1.handleError)("No events found in the uploaded file.", 400, errrorcode_1.errorCode.invalid);
    }
    return events;
}
function detectFormat(text, originalName, mimetype) {
    const extension = originalName.split(".").pop()?.toLowerCase();
    if (extension === "jsonl" || extension === "ndjson")
        return "jsonl";
    if (extension === "json")
        return "json";
    if (extension === "csv")
        return "csv";
    if (mimetype.includes("csv"))
        return "csv";
    if (mimetype.includes("json"))
        return "json";
    const firstLine = text.split(/\r?\n/, 1)[0]?.trim() || "";
    const firstCharacter = firstLine[0];
    if (firstCharacter === "[" || firstCharacter === "{") {
        try {
            JSON.parse(text);
            return "json";
        }
        catch {
            return "jsonl";
        }
    }
    if (firstLine.includes(","))
        return "csv";
    return "jsonl";
}
function parseJson(text) {
    let parsed;
    try {
        parsed = JSON.parse(text);
    }
    catch (error) {
        throw (0, errorHandeling_1.handleError)(`Invalid JSON file: ${error instanceof Error ? error.message : "parse error"}`, 400, errrorcode_1.errorCode.invalid);
    }
    if (Array.isArray(parsed))
        return parsed;
    if (parsed && typeof parsed === "object") {
        for (const key of ["events", "logs", "records", "items", "data"]) {
            if (Array.isArray(parsed[key]))
                return parsed[key];
        }
        return [parsed];
    }
    throw (0, errorHandeling_1.handleError)("JSON file must contain an object or an array of objects.", 400, errrorcode_1.errorCode.invalid);
}
function parseJsonLines(text) {
    const events = [];
    const lines = text.split(/\r?\n/);
    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index].trim();
        if (!line)
            continue;
        try {
            events.push(JSON.parse(line));
        }
        catch (error) {
            throw (0, errorHandeling_1.handleError)(`Invalid JSON on line ${index + 1}: ${error instanceof Error ? error.message : "parse error"}`, 400, errrorcode_1.errorCode.invalid);
        }
    }
    return events;
}
function parseCsv(text) {
    const rows = parseCsvRows(text);
    if (rows.length === 0)
        return [];
    const headers = rows[0].map((header) => header.trim());
    if (headers.every((header) => header === "")) {
        throw (0, errorHandeling_1.handleError)("CSV file is missing a header row.", 400, errrorcode_1.errorCode.invalid);
    }
    const events = [];
    for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
        const row = rows[rowIndex];
        if (row.every((value) => value.trim() === ""))
            continue;
        const event = {};
        for (let columnIndex = 0; columnIndex < headers.length; columnIndex += 1) {
            const header = headers[columnIndex];
            if (!header)
                continue;
            event[header] = row[columnIndex] ?? "";
        }
        events.push(event);
    }
    return events;
}
function parseCsvRows(text) {
    const rows = [];
    let row = [];
    let value = "";
    let inQuotes = false;
    for (let index = 0; index < text.length; index += 1) {
        const character = text[index];
        if (inQuotes) {
            if (character === '"') {
                if (text[index + 1] === '"') {
                    value += '"';
                    index += 1;
                }
                else {
                    inQuotes = false;
                }
            }
            else {
                value += character;
            }
            continue;
        }
        if (character === '"') {
            inQuotes = true;
        }
        else if (character === ",") {
            row.push(value);
            value = "";
        }
        else if (character === "\n") {
            row.push(value);
            rows.push(row);
            row = [];
            value = "";
        }
        else if (character === "\r") {
            if (text[index + 1] !== "\n") {
                row.push(value);
                rows.push(row);
                row = [];
                value = "";
            }
        }
        else {
            value += character;
        }
    }
    if (value !== "" || row.length > 0) {
        row.push(value);
        rows.push(row);
    }
    return rows;
}
//# sourceMappingURL=batch.js.map