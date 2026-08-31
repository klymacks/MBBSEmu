using MBBSEmu.Memory;
using System.Text;
using Xunit;

namespace MBBSEmu.Tests.ExportedModules.Majorbbs
{
    /// <summary>
    ///     Verifies that the BBS identity strings a Module reads through the MAJORBBS
    ///     globals (BBSTTL, COMPANY, ADDRES1, ADDRES2, DATAPH, LIVEPH) reflect the
    ///     operator's appsettings.json values rather than hard-coded defaults.
    ///
    ///     These are the same globals a module such as MajorMUD reads to display the
    ///     board's name/company/address, so this is the emulator-side equivalent of
    ///     reading the BBS string from within a running module.
    ///
    ///     The expected values come from the test project's appsettings.json.
    /// </summary>
    public class bbsIdentity_Tests : ExportedModuleTestBase
    {
        private const ushort BBSTTL_ORDINAL = 83;
        private const ushort COMPANY_ORDINAL = 136;
        private const ushort ADDRES1_ORDINAL = 61;
        private const ushort ADDRES2_ORDINAL = 62;
        private const ushort DATAPH_ORDINAL = 153;
        private const ushort LIVEPH_ORDINAL = 387;

        [Theory]
        [InlineData(BBSTTL_ORDINAL, "Test")]
        [InlineData(COMPANY_ORDINAL, "Cursor Retro Systems")]
        [InlineData(ADDRES1_ORDINAL, "123 Emulator Way")]
        [InlineData(ADDRES2_ORDINAL, "Terminal City, TX 75001")]
        [InlineData(DATAPH_ORDINAL, "(555) 867-5309")]
        [InlineData(LIVEPH_ORDINAL, "(555) 555-0100")]
        public void GlobalReturnsConfiguredValue(ushort ordinal, string expected)
        {
            Reset();

            //These globals are char* values: the property ordinal resolves to the
            //address of the pointer variable (*VAR), which holds the address of the
            //actual string bytes. Dereference once to read the string, exactly as a
            //module's relocated code would.
            var pointerVariable = new FarPtr(ExecutePropertyTest(ordinal));
            var stringPointer = mbbsEmuMemoryCore.GetPointer(pointerVariable);
            var actual = Encoding.ASCII.GetString(mbbsEmuMemoryCore.GetString(stringPointer, stripNull: true));

            Assert.Equal(expected, actual);
        }
    }
}
