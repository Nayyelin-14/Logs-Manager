"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const sampleData_1 = require("./sampleData");
const PrismaClient_1 = require("./PrismaClient");
async function main() {
    console.log("Starting seeding...");
    // Clear existing data
    await PrismaClient_1.prisma.securityEvent.deleteMany();
    await PrismaClient_1.prisma.user.deleteMany();
    // Insert logs
    await PrismaClient_1.prisma.securityEvent.createMany({ data: sampleData_1.sample_seed_data.sampleLogs });
    // Hash passwords and insert users
    const usersToInsert = await Promise.all(sampleData_1.sample_seed_data.sampleUsers.map(async (user) => ({
        ...user,
        password: await (0, sampleData_1.hashedPassword)("defaultPassword123"), // set a default password
    })));
    await PrismaClient_1.prisma.user.createMany({ data: usersToInsert });
    console.log("Seeding finished.");
}
main()
    .then(() => PrismaClient_1.prisma.$disconnect())
    .catch(async (e) => {
    console.error(e);
    await PrismaClient_1.prisma.$disconnect();
    process.exit(1);
});
//# sourceMappingURL=seed.js.map