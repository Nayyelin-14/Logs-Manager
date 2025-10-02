import { AlertRule, PrismaClient } from "../generated/prisma";

const prisma = new PrismaClient();

export interface CreateAlertRuleInput {
  name: string;
  description?: string;
  tenant: string;
  enabled?: boolean;
  conditions: any[]; // array of condition objects
  actions?: Record<string, any>;
}
// Get one alert rule by tenant+name OR by id
export const getExistedAlertRule = async (where: {
  tenant?: string;
  name?: string;
  id?: string;
}) => {
  return await prisma.alertRule.findMany({ where });
};

export const getAllRules = async (options: any) => {
  const { where, skip, take, cursor, orderBy, select } = options;
  return prisma.alertRule.findMany({
    where: where || {},
    skip,
    take,
    cursor,
    orderBy,
    select,
  });
};
// Create a new AlertRule
export const createNewAlertRule = async (
  data: CreateAlertRuleInput
): Promise<AlertRule> => {
  const {
    name,
    description,
    tenant,

    conditions,
  } = data;

  const alertRule = await prisma.alertRule.create({
    data: {
      name,
      description,
      tenant,
      conditions,
    },
  });

  return alertRule;
};

// Delete an existing AlertRule by id
export const deleteExistedAlert = async (id: string) => {
  return prisma.alertRule.delete({
    where: { id },
  });
};

export const duplicate = (tenant?: string, name?: string, id?: string) => {
  return prisma.alertRule.findFirst({
    where: {
      tenant,
      name,
      NOT: { id }, // exclude current rule
    },
  });
};

export const updateAlertRuleById = async (
  data: CreateAlertRuleInput,
  id: string
) => {
  return prisma.alertRule.update({
    where: { id },
    data,
  });
};
