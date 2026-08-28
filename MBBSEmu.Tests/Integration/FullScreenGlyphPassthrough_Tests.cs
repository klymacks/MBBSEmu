using FluentAssertions;
using System;
using System.Text;
using Xunit;

namespace MBBSEmu.Tests.Integration
{
    /// <summary>
    ///     Counterpart to <see cref="ScreenPause_Tests"/>: full-screen painting is
    ///     GSBL binary-mode output, where 0x11-0x14 are CP437 display glyphs rather
    ///     than screen-pause markers (MajorMUD's FSD worksheet draws its sliders with
    ///     them, see #553). Consumption must not apply there. The test module's Full
    ///     Screen Data Editor paints all four between the User-ID and Name fields.
    /// </summary>
    [Collection("Non-Parallel")]
    public class FullScreenGlyphPassthrough_Tests : MBBSEmuIntegrationTestBase
    {
        [Fact]
        public void GlyphsSurviveFullScreenPainting()
        {
            ExecuteTest((session, host) =>
            {
                WaitUntil(':', "Make your selection");
                session.SendToModule(Encoding.ASCII.GetBytes("D\r\n"));
                var painted = session.DrainSentData(TimeSpan.FromSeconds(3));

                session.SessionState.ToString().Should().Contain("FullScreen",
                    "the Data Editor should paint from a full-screen session state");

                //Non-vacuous: the worksheet really painted rather than erroring out
                Encoding.ASCII.GetString(painted).Should().Contain("User Account Information");

                //0x13 and 0x14 are the armed screen-pause defaults; in binary-mode
                //full-screen output they are display glyphs and must pass through
                painted.Should().Contain((byte)0x11).And.Contain((byte)0x12);
                painted.Should().Contain((byte)0x13).And.Contain((byte)0x14);
            });
        }
    }
}
