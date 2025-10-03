import { PrismaClient } from "../generated/prisma";
import { sample_seed_data, hashedPassword } from "./sampleData";

const prisma = new PrismaClient();

async function main() {
  console.log("Starting seeding...");

  // Clear existing data
  await prisma.securityEvent.deleteMany();
  await prisma.user.deleteMany();

  // Insert logs
  await prisma.securityEvent.createMany({ data: sample_seed_data.sampleLogs });

  // Hash passwords and insert users
  const usersToInsert = await Promise.all(
    sample_seed_data.sampleUsers.map(async (user) => ({
      ...user,
      password: await hashedPassword("defaultPassword123"), // set a default password
    }))
  );

  await prisma.user.createMany({ data: usersToInsert });

  console.log("Seeding finished.");
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
