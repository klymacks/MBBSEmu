using FluentAssertions;
using MBBSEmu.Tests.Util;
using System;
using System.Text;
using Xunit;

namespace MBBSEmu.Tests.Integration
{
    /// <summary>
    ///     Wire-invariant tests for GSBL screen-pause markers. Modules embed the
    ///     pause and clear-pause-counter characters in their output and rely on the
    ///     host to consume them; real MajorBBS 6.25 transmits none of 0x11-0x14 over
    ///     the equivalent T-LORD journey. The test module's Output playground drives
    ///     the same mechanism: it prints a line carrying a raw 0x13, then registers a
    ///     replacement character through btupbc and prints the line again using it.
    /// </summary>
    [Collection("Non-Parallel")]
    public class ScreenPause_Tests : MBBSEmuIntegrationTestBase
    {
        [Fact]
        public void DefaultClearPauseCounterCharacterIsConsumed()
        {
            ExecuteTest((session, host) =>
            {
                WaitUntil(':', "Make your selection");
                session.SendToModule(Encoding.ASCII.GetBytes("O\r\n"));
                WaitUntil(':', "Enter the pause character");
                session.DrainSentData(TimeSpan.FromSeconds(2));

                //0x41 ('A') so the second line's marker is visible as a printable byte
                session.SendToModule(Encoding.ASCII.GetBytes("0x41\r\n"));
                var wire = session.DrainSentData(TimeSpan.FromSeconds(3));
                var text = Encoding.ASCII.GetString(wire);

                //Non-vacuous: the module really did print the line carrying the marker
                text.Should().Contain("Test output with embedded 0x13",
                    "the module prints its marker-carrying line before calling btupbc");

                //0x13 is armed host-side by default, so it never reaches the wire
                GoldenAssert.ContainsNone(wire, 0x13);
            });
        }

        [Fact]
        public void BtupbcRegisteredCharacterIsConsumed()
        {
            ExecuteTest((session, host) =>
            {
                WaitUntil(':', "Make your selection");
                session.SendToModule(Encoding.ASCII.GetBytes("O\r\n"));
                WaitUntil(':', "Enter the pause character");
                session.DrainSentData(TimeSpan.FromSeconds(2));

                session.SendToModule(Encoding.ASCII.GetBytes("0x41\r\n"));
                var wire = session.DrainSentData(TimeSpan.FromSeconds(3));
                var text = Encoding.ASCII.GetString(wire);

                //After btupbc(usrnum, 0x41) the module reprints the same line with 'A'
                //in the marker position. Consumption removes it, so the words close up.
                text.Should().Contain("Test output with embedded 0x41",
                    "the registered pause character is consumed from the reprinted line");
                text.Should().NotContain("Test outputA with",
                    "an unconsumed marker would leave the 'A' between the words");
            });
        }
    }
}
