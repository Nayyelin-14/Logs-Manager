import { randomBytes } from "crypto";
export const generateOTP = () => {
  //toString("hex") and parseInt(..., 16):
  // Converts the 3 bytes to a hexadecimal string, then parses it into a decimal integer.For example: "f1b2c3" → 15866115.
  return (parseInt(randomBytes(3).toString("hex"), 16) % 900000) + 100000;
};

export const generateToken = () => {
  return randomBytes(32).toString("hex");
};
