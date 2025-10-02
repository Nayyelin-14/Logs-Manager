import { PrismaClient } from "../generated/prisma";

const prisma = new PrismaClient();

export const getUserByEmail = async (email: string) => {
  return prisma.user.findUnique({
    where: {
      email,
    },
  });
};

export const getOtpByEmail = async (email: string) => {
  return prisma.otp.findUnique({
    where: {
      email,
    },
  });
};
export const storeOtp = (optData: any) => {
  return prisma.otp.create({
    data: optData,
  });
};
export const updateOtp = (optData: any, id: number) => {
  return prisma.otp.update({
    where: { id },
    data: optData,
  });
};

export const createNewUser = (userData: any) => {
  return prisma.user.create({
    data: userData,
  });
};

export const updateUser = (userData: any, id: number) => {
  return prisma.user.update({
    where: { id },
    data: userData,
  });
};
export const getUserById = async (id: number) => {
  return prisma.user.findUnique({
    where: {
      id,
    },
  });
};

export const deleteUserById = async (id: number) => {
  return prisma.user.delete({ where: { id } });
};
export const getAllUserListByPagi = async (options: any) => {
  return await prisma.user.findMany(options);
};
