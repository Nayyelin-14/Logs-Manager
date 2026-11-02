import { prisma } from "../config/PrismaClient";
export const getAllLogsListByPagi = async (options: any) => {
  return await prisma.securityEvent.findMany(options);
};

export const getLogById = async (id: string) => {
  return prisma.securityEvent.findUnique({
    where: {
      id,
    },
  });
};

export const deleteLogById = async (id: string) => {
  return prisma.securityEvent.delete({ where: { id } });
};
